from datetime import datetime, timezone

import discord
from discord.ext import commands

import config
import db


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def verify(self, ctx):
        guild, user = ctx.guild, ctx.author

        unverified = discord.utils.get(guild.roles, name=config.UNVERIFIED_ROLE)
        confirmed = discord.utils.get(guild.roles, name=config.CONFIRMED_ROLE)

        if confirmed in user.roles:
            await ctx.send("✅ You are already verified.")
            return

        if unverified not in user.roles:
            await ctx.send("⚠️ You cannot use this command.")
            return

        if db.verifications.find_one({"user_id": str(user.id), "status": "pending"}):
            await ctx.send("⏳ You already have a pending verification request.")
            return

        if not ctx.message.attachments:
            await ctx.send(
                "📎 Please upload your signed Newton document.\n"
                "Accepted formats: **PDF, PNG**\n"
                "Example:\n`!verify` + attach file"
            )
            return

        attachment = ctx.message.attachments[0]
        ext = attachment.filename.lower().rsplit(".", 1)[-1]

        if ext not in config.ALLOWED_EXTENSIONS:
            await ctx.send(
                "❌ Invalid file format.\n"
                "Accepted formats: **PDF (.pdf)** or **PNG (.png)** only."
            )
            return

        queue_channel = discord.utils.get(
            guild.text_channels, name=config.VERIFICATION_CHANNEL
        )
        if not queue_channel:
            await ctx.send("❌ Verification system misconfigured. Contact admin.")
            return

        embed = discord.Embed(
            title="📝 New Verification Submission",
            description=(
                f"👤 User: {user.mention}\n"
                f"🆔 ID: `{user.id}`\n"
                f"📂 File: `{attachment.filename}`"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Use !approve @user or !reject @user")

        msg = await queue_channel.send(embed=embed)
        await queue_channel.send(file=await attachment.to_file())

        db.verifications.insert_one(
            {
                "user_id": str(user.id),
                "username": str(user),
                "file_url": attachment.url,
                "file_name": attachment.filename,
                "file_type": ext,
                "status": "pending",
                "submitted_at": datetime.now(timezone.utc),
                "reviewed_at": None,
                "reviewed_by": None,
                "reason": None,
                "queue_message_id": str(msg.id),
            }
        )

        await ctx.send("📨 Your document has been submitted for verification.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def approve(self, ctx, member: discord.Member):
        record = db.verifications.find_one(
            {"user_id": str(member.id), "status": "pending"}
        )
        if not record:
            await ctx.send("No pending verification found for this user.")
            return

        unverified = discord.utils.get(ctx.guild.roles, name=config.UNVERIFIED_ROLE)
        confirmed = discord.utils.get(ctx.guild.roles, name=config.CONFIRMED_ROLE)

        await member.add_roles(confirmed)
        if unverified in member.roles:
            await member.remove_roles(unverified)

        db.verifications.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "status": "approved",
                    "reviewed_at": datetime.now(timezone.utc),
                    "reviewed_by": str(ctx.author.id),
                }
            },
        )

        await ctx.send(f"{member.mention} has been verified!")
        await self.bot.dm(member,"🎉 Your NST verification is approved! Welcome aboard.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def reject(self, ctx, member: discord.Member, *, reason="No reason provided"):
        record = db.verifications.find_one(
            {"user_id": str(member.id), "status": "pending"}
        )
        if not record:
            await ctx.send("No pending verification found for this user.")
            return

        db.verifications.update_one(
            {"_id": record["_id"]},
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
        await self.bot.dm(member,f"Your NST verification was rejected.\nReason: {reason}")


async def setup(bot):
    await bot.add_cog(Verification(bot))
