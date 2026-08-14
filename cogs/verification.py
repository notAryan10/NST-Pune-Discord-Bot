"""Roster-backed verification.

The exchange happens in DMs. A URN embeds the student's date of birth, so prompting
for one in a public channel would publish it to everyone reading.

Identity comes from the URN, which is unique per student and claimable exactly once.
The name is only a confirmation signal — it cannot identify anyone, because some
names in the roster belong to two different students.
"""
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

import config
import db
import roster
from cogs.batch import current_academic_year, year_role_for


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- attempt limiting ------------------------------------------------------

    def locked_until(self, user_id):
        """The moment this user may try again, or None if they are not locked out."""
        row = db.verify_attempts.find_one({"user_id": user_id})
        if not row or not row.get("locked_until"):
            return None
        until = row["locked_until"].replace(tzinfo=timezone.utc)
        return until if until > datetime.now(timezone.utc) else None

    def record_failure(self, user_id):
        """Count a miss and lock the user out once they have burned their attempts."""
        row = db.verify_attempts.find_one_and_update(
            {"user_id": user_id},
            {"$inc": {"failures": 1}, "$set": {"last_failed_at": datetime.now(timezone.utc)}},
            upsert=True,
            return_document=True,
        )
        if row["failures"] >= config.VERIFY_MAX_ATTEMPTS:
            until = datetime.now(timezone.utc) + timedelta(
                minutes=config.VERIFY_LOCKOUT_MINUTES
            )
            db.verify_attempts.update_one(
                {"user_id": user_id}, {"$set": {"locked_until": until, "failures": 0}}
            )
            return until
        return None

    def clear_failures(self, user_id):
        db.verify_attempts.delete_one({"user_id": user_id})

    # --- helpers ---------------------------------------------------------------

    async def ask(self, dm, user, prompt):
        """Send a DM prompt and wait for that user's next DM. None on timeout."""
        await dm.send(prompt)

        def check(m):
            return m.author == user and m.channel == dm

        try:
            reply = await self.bot.wait_for(
                "message", timeout=config.VERIFY_REPLY_TIMEOUT, check=check
            )
        except TimeoutError:
            await dm.send("⏳ Timed out. Run `!verify` in the server to start again.")
            return None
        return reply.content.strip()

    def queue_channel(self, guild):
        return discord.utils.get(guild.text_channels, name=config.VERIFICATION_CHANNEL)

    async def grant(self, member, record, method, score):
        """Assign roles, claim the roster row, and write the audit trail.

        The claim is a conditional update: it only succeeds if the row is still
        unclaimed, so two submissions racing on one URN cannot both win.
        """
        claimed = db.roster.update_one(
            {"urn": record["urn"], "claimed_by": None},
            {
                "$set": {
                    "claimed_by": str(member.id),
                    "claimed_at": datetime.now(timezone.utc),
                }
            },
        )
        if not claimed.modified_count:
            return False

        guild = member.guild
        confirmed = discord.utils.get(guild.roles, name=config.CONFIRMED_ROLE)
        unverified = discord.utils.get(guild.roles, name=config.UNVERIFIED_ROLE)

        if confirmed:
            await member.add_roles(confirmed)
        if unverified and unverified in member.roles:
            await member.remove_roles(unverified)

        # The roster already tells us the admission year, so the year role needs no
        # separate !batch round-trip.
        role_name = year_role_for(record["admission_year"])
        role = discord.utils.get(guild.roles, name=role_name) if role_name else None

        if role:
            await member.add_roles(role)
        elif role_name:
            # The year is valid but the server has no such role yet. Verification
            # still stands — being a student does not depend on the role existing —
            # but somebody needs to know, or the cohort silently goes untagged.
            queue = self.queue_channel(guild)
            if queue:
                await queue.send(
                    f"⚠️ Verified {member.mention} but the **{role_name}** role "
                    f"doesn't exist on this server. Create it and assign it manually."
                )

        if role_name:
            db.batches.update_one(
                {"user_id": str(member.id)},
                {
                    "$setOnInsert": {
                        "name": record["name"],
                        "urn": record["urn_raw"],
                        "admission_year": record["admission_year"],
                        "academic_year_number": current_academic_year()
                        - record["admission_year"]
                        + 1,
                        "assigned_role": role_name,
                        "submitted_at": datetime.now(timezone.utc),
                        "source": "roster",
                    }
                },
                upsert=True,
            )

        db.verifications.update_one(
            {"user_id": str(member.id), "urn": record["urn"]},
            {
                "$set": {
                    "username": str(member),
                    "status": "approved",
                    "method": method,
                    "match_score": score,
                    "roster_name": record["name"],
                    "reviewed_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        self.clear_failures(str(member.id))
        return True

    # --- commands --------------------------------------------------------------

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def verify(self, ctx):
        if ctx.guild is None:
            await ctx.send("Run `!verify` in the server and I'll continue here.")
            return

        guild, user = ctx.guild, ctx.author
        confirmed = discord.utils.get(guild.roles, name=config.CONFIRMED_ROLE)

        if confirmed and confirmed in user.roles:
            await ctx.send("✅ You are already verified.")
            return

        until = self.locked_until(str(user.id))
        if until:
            mins = max(1, int((until - datetime.now(timezone.utc)).total_seconds() // 60))
            await ctx.send(f"🔒 Too many failed attempts. Try again in {mins} min.")
            return

        if db.verifications.find_one({"user_id": str(user.id), "status": "pending"}):
            await ctx.send("⏳ You already have a request waiting for review.")
            return

        try:
            dm = await user.create_dm()
            await dm.send(
                "👋 Let's get you verified.\n"
                "I'll ask for your **URN** and your **full name**, and check them "
                "against the official student list.\n"
                "We're doing this in DMs because your URN contains your date of birth."
            )
        except discord.Forbidden:
            await ctx.send(
                "❌ I couldn't DM you. Enable **Settings → Privacy → Direct Messages** "
                "for this server, then run `!verify` again."
            )
            return

        await ctx.send(f"📬 {user.mention} check your DMs.")
        await self.run_flow(dm, guild, user)

    async def run_flow(self, dm, guild, user):
        urn_raw = await self.ask(dm, user, "🔢 What's your **URN**? (e.g. `2024-B-13072005B`)")
        if urn_raw is None:
            return

        if not roster.looks_like_urn(urn_raw):
            await dm.send(
                "❌ That doesn't look like a URN.\n"
                "Expected something like `2024-B-13072005B`. Run `!verify` to retry."
            )
            self.record_failure(str(user.id))
            return

        record = roster.find(urn_raw)
        if not record:
            await dm.send(
                "❌ That URN isn't on the student list I have.\n"
                "Check it against your ID card, or contact an admin if it's correct."
            )
            self.record_failure(str(user.id))
            return

        if record.get("claimed_by"):
            if record["claimed_by"] == str(user.id):
                await dm.send("✅ You're already verified with that URN.")
                return
            await dm.send(
                "⚠️ That URN has already been used to verify another account.\n"
                "An admin has been notified — contact them if this is your URN."
            )
            queue = self.queue_channel(guild)
            if queue:
                await queue.send(
                    f"🚨 {user.mention} (`{user.id}`) tried to verify with `{record['urn_raw']}`, "
                    f"already claimed by <@{record['claimed_by']}>."
                )
            self.record_failure(str(user.id))
            return

        if db.verifications.find_one({"urn": record["urn"], "status": "pending"}):
            await dm.send("⏳ That URN already has a request waiting for review.")
            return

        name_raw = await self.ask(dm, user, "📝 And your **full name**, as the college has it?")
        if name_raw is None:
            return

        score = roster.score_name(name_raw, record)
        outcome = roster.decide(score, record)

        if outcome == roster.AUTO:
            member = guild.get_member(user.id)
            if member and await self.grant(member, record, "auto", score):
                await dm.send("🎉 Verified! Your roles are set — welcome aboard.")
                return
            outcome = roster.REVIEW  # lost the race, or left the server; let a human look

        if outcome == roster.REJECT:
            await dm.send(
                "❌ That name doesn't match the one on record for that URN.\n"
                "Check your spelling and run `!verify` again, or contact an admin."
            )
            self.record_failure(str(user.id))
            return

        db.verifications.update_one(
            {"user_id": str(user.id), "urn": record["urn"]},
            {
                "$set": {
                    "username": str(user),
                    "submitted_name": name_raw,
                    "roster_name": record["name"],
                    "match_score": score,
                    "status": "pending",
                    "method": "review",
                    "submitted_at": datetime.now(timezone.utc),
                    "reviewed_at": None,
                    "reviewed_by": None,
                    "reason": None,
                }
            },
            upsert=True,
        )

        queue = self.queue_channel(guild)
        if queue:
            embed = discord.Embed(
                title="📝 Verification needs review",
                description=(
                    f"👤 {user.mention} · `{user.id}`\n"
                    f"🔢 URN: `{record['urn_raw']}`\n"
                    f"📄 On roster: **{record['name']}**\n"
                    f"✍️ They typed: **{name_raw}**\n"
                    f"📊 Match: **{score}%**"
                ),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="!approve @user  ·  !reject @user [reason]")
            await queue.send(embed=embed)

        await dm.send(
            "📨 Close, but not close enough for me to be sure — I've sent it to an "
            "admin. You'll get a DM once it's reviewed."
        )

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def approve(self, ctx, member: discord.Member):
        pending = db.verifications.find_one(
            {"user_id": str(member.id), "status": "pending"}
        )
        if not pending:
            await ctx.send("No pending verification found for this user.")
            return

        record = db.roster.find_one({"urn": pending["urn"]})
        if not record:
            await ctx.send("⚠️ That roster entry no longer exists. Re-import the roster.")
            return

        if not await self.grant(member, record, "manual", pending.get("match_score")):
            await ctx.send("⚠️ That URN was claimed by someone else in the meantime.")
            return

        db.verifications.update_one(
            {"_id": pending["_id"]}, {"$set": {"reviewed_by": str(ctx.author.id)}}
        )
        await ctx.send(f"✅ {member.mention} has been verified.")
        await self.bot.dm(member, "🎉 Your NST verification is approved! Welcome aboard.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def reject(self, ctx, member: discord.Member, *, reason="No reason provided"):
        pending = db.verifications.find_one(
            {"user_id": str(member.id), "status": "pending"}
        )
        if not pending:
            await ctx.send("No pending verification found for this user.")
            return

        db.verifications.update_one(
            {"_id": pending["_id"]},
            {
                "$set": {
                    "status": "rejected",
                    "reviewed_at": datetime.now(timezone.utc),
                    "reviewed_by": str(ctx.author.id),
                    "reason": reason,
                }
            },
        )
        await ctx.send(f"❌ {member.mention}'s verification was rejected.")
        await self.bot.dm(member, f"Your NST verification was rejected.\nReason: {reason}")


async def setup(bot):
    await bot.add_cog(Verification(bot))
