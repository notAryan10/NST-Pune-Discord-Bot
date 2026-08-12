import discord
from discord.ext import commands

import config


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role = discord.utils.get(member.guild.roles, name=config.UNVERIFIED_ROLE)
        if role:
            await member.add_roles(role)

    async def screen(self, message):
        """Delete and warn on profanity. Returns True if the message was removed.

        Called from NSTBot.on_message so a deleted message never reaches the command
        parser or the help desk.
        """
        msg = message.content.lower()
        if not any(word in msg for word in config.BAD_WORDS):
            return False

        await message.delete()
        await message.channel.send(
            f"{message.author.mention} ⚠️ Please avoid inappropriate language."
        )
        return True


async def setup(bot):
    await bot.add_cog(Moderation(bot))
