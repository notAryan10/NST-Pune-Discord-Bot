from datetime import datetime, timezone

import discord
from discord.ext import commands

import config
import db


def current_academic_year(now=None):
    """The academic year rolls over in July."""
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def parse_urn(urn):
    """Return the admission year from a URN like '2024-B-123456789B', or None if malformed."""
    urn = urn.strip().upper()
    if len(urn) < 6 or not urn[:4].isdigit():
        return None
    return int(urn[:4])


def year_role_for(admission_year, today=None):
    """Map an admission year to a year role name, or None if outside years 1-4."""
    return config.YEAR_MAP.get(current_academic_year(today) - admission_year + 1)


class Batch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def ask_for(self, ctx, prompt):
        """Send a prompt and wait 60s for the same user in the same channel."""
        await ctx.send(prompt)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await self.bot.wait_for("message", timeout=60.0, check=check)
        except TimeoutError:
            await ctx.send("⏳ Timed out. Please run `!batch` again.")
            return None
        return reply.content.strip()

    @commands.command()
    async def batch(self, ctx):
        guild, user = ctx.guild, ctx.author

        confirmed = discord.utils.get(guild.roles, name=config.CONFIRMED_ROLE)
        if confirmed not in user.roles:
            await ctx.send("You must be verified before setting your batch.")
            return

        existing = db.batches.find_one({"user_id": str(user.id)})
        if existing:
            await ctx.send(
                f"🔒 You already submitted your batch info.\n"
                f"Assigned role: **{existing['assigned_role']}**\n"
                "Contact admin if incorrect."
            )
            return

        full_name = await self.ask_for(ctx, "📝 Please enter your **Full Name**:")
        if full_name is None:
            return

        urn = await self.ask_for(
            ctx, "🔢 Now enter your **URN Number** (e.g. `2024-B-123456789B`):"
        )
        if urn is None:
            return

        urn = urn.upper()
        admission_year = parse_urn(urn)
        if admission_year is None:
            await ctx.send("❌ Invalid URN format.\nExpected format: `2024-B-XXXXXXXX`")
            return

        role_name = year_role_for(admission_year)
        if role_name is None:
            await ctx.send(
                "Your URN does not map to a valid academic year.\n"
                "Contact admin for manual review."
            )
            return

        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            await ctx.send("❌ Year role not found. Contact Admin.")
            return

        await user.add_roles(role)

        academic_year = current_academic_year()
        db.batches.insert_one(
            {
                "user_id": str(user.id),
                "name": full_name,
                "urn": urn,
                "admission_year": admission_year,
                "academic_year_number": academic_year - admission_year + 1,
                "assigned_role": role_name,
                "submitted_at": datetime.now(timezone.utc),
            }
        )

        await ctx.send(
            f"✅ Batch verified!\n"
            f"👤 Name: **{full_name}**\n"
            f"🎓 Admission Year: **{admission_year}**\n"
            f"📆 Current Academic Year: **{academic_year}**\n"
            f"📌 Assigned Role: **{role_name}**\n\n"
            "🔒 This cannot be changed. Contact Admin if incorrect."
        )

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Year roles are locked: strip a second year role if one was already held."""
        before_years = {r.name for r in before.roles} & config.YEAR_ROLES
        after_years = {r.name for r in after.roles} & config.YEAR_ROLES

        added = after_years - before_years
        # Only act on a newly added year role when the member already had one.
        # Everything else (nickname edits, other roles, our own removal below) is a no-op.
        if not added or not before_years:
            return

        role = discord.utils.get(after.guild.roles, name=added.pop())
        if role:
            await after.remove_roles(role)

        await self.bot.dm(after, "🔒 Year roles are locked. Contact Admin for changes.")


async def setup(bot):
    await bot.add_cog(Batch(bot))
