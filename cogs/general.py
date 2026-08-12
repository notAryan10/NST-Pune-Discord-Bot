from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong! Bot is working.")

    @commands.command()
    async def test(self, ctx, *, arg):
        await ctx.send(arg)

    @commands.command()
    async def add(self, ctx, a: int, b: int):
        await ctx.send(f"Result: {a + b}")


async def setup(bot):
    await bot.add_cog(General(bot))
