import logging

import aiohttp
from discord.ext import commands

import assistant


class Helpdesk(commands.Cog):
    """The AI layer. Answers questions; never changes anything."""

    def __init__(self, bot):
        self.bot = bot

    async def respond(self, channel, author, question):
        if not question:
            await channel.send("Ask me something, e.g. `!ask how do I get verified?`")
            return

        async with channel.typing():
            try:
                text = await assistant.answer(question, author)
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    await channel.send(
                        "😅 I'm getting a lot of questions right now — give me a minute "
                        "and ask again."
                    )
                    return
                logging.exception("helpdesk answer failed")
                await channel.send(
                    "I couldn't reach the assistant right now. Try again, or ask an admin."
                )
                return
            except Exception:
                logging.exception("helpdesk answer failed")
                await channel.send(
                    "I couldn't reach the assistant right now. Try again, or ask an admin."
                )
                return

        await channel.send(text)

    async def handle_mention(self, message):
        # Strip the raw mention token, not clean_content's "@Name" — that renders the
        # server nickname, which won't match bot.user.name.
        question = message.content
        for token in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
            question = question.replace(token, "")
        await self.respond(message.channel, message.author, question.strip())

    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def ask(self, ctx, *, question=""):
        await self.respond(ctx.channel, ctx.author, question)


async def setup(bot):
    await bot.add_cog(Helpdesk(bot))
