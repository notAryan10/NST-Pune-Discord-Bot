"""NST-Bot entrypoint: builds the bot, loads cogs, runs."""
import logging

import discord
from discord.ext import commands

import config

COGS = ["general", "moderation", "verification", "batch", "helpdesk"]


class NSTBot(commands.Bot):
    async def setup_hook(self):
        for name in COGS:
            await self.load_extension(f"cogs.{name}")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Loaded cogs: {', '.join(self.cogs)}")

    async def on_message(self, message):
        """Single dispatch point, so moderation runs before anything else sees the message."""
        if message.author == self.user:
            return

        if await self.get_cog("Moderation").screen(message):
            return

        # A mention that isn't a command goes to the help desk.
        if self.user in message.mentions and not message.content.startswith(
            config.COMMAND_PREFIX
        ):
            await self.get_cog("Helpdesk").handle_mention(message)
            return

        await self.process_commands(message)

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⛔ You don't have permission to use that command.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down — try again in {error.retry_after:.0f}s.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing `{error.param.name}`. Usage: `!{ctx.command} ...`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("⚠️ I couldn't understand that argument.")
        else:
            logging.exception("command %s failed", ctx.command, exc_info=error)
            await ctx.send("❌ Something went wrong. An admin should check the logs.")

    async def dm(self, member, text):
        """Best-effort DM. Members can have DMs closed; not an error worth raising."""
        try:
            await member.send(text)
        except discord.HTTPException:
            pass


def build_bot():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    return NSTBot(command_prefix=config.COMMAND_PREFIX, intents=intents)


if __name__ == "__main__":
    handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
    build_bot().run(config.DISCORD_TOKEN, log_handler=handler, log_level=logging.INFO)
