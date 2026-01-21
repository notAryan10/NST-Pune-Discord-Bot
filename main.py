import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import aiofiles
import uuid

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BAD_WORDS = ["shit", "fuck"]

UNVERIFIED_ROLE = "Unverified"
CONFIRMED_ROLE = "Confirmed Student"
VERIFICATION_CHANNEL = "verification-queue"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is online and ready")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()

    for word in BAD_WORDS:
        if word in msg:
            await message.delete()
            await message.channel.send(f"{message.author.mention} Please avoid using inappropriate language.")
            return 
    await bot.process_commands(message)


@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong! Bot is working.")

@bot.command()
async def test(ctx, *, arg):
    await ctx.send(arg)

@bot.command()
async def add(ctx, a: int, b: int):
    await ctx.send(f"Result: {a + b}")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role:
        await member.add_roles(role)
        await ctx.send(f"{member.mention} has been muted.")

@bot.command()
async def applyclub(ctx, club_name):
    await ctx.send(f"Your request to join **{club_name}** has been sent to coordinators.")


@bot.command()
async def verify(ctx):
    guild = ctx.guild
    user = ctx.author

    unverified = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE)
    confirmed = discord.utils.get(guild.roles, name=CONFIRMED_ROLE)

    if confirmed in user.roles:
        await ctx.send("✅ You are already verified.")
        return

    if unverified not in user.roles:
        await ctx.send("⚠️ You cannot use this command.")
        return

    if not ctx.message.attachments:
        await ctx.send("📎 Please upload your signed Newton document with this command.\nExample:\n`!verify` + attach file")
        return

    attachment = ctx.message.attachments[0]

    ext = attachment.filename.split(".")[-1]
    filename = f"{user.id}_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(await attachment.read())

    queue_channel = discord.utils.get(guild.text_channels, name=VERIFICATION_CHANNEL)

    if queue_channel:
        embed = discord.Embed(
            title="📝 New Verification Submission",
            description=(
                f"User: {user.mention}\n"
                f"ID: `{user.id}`\n"
                f"File: `{filename}`"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Use !approve @user or !reject @user")

        file = discord.File(filepath)
        await queue_channel.send(embed=embed, file=file)

    await ctx.send("📨 Your document has been submitted for verification. Please wait for admin approval.")


@bot.command()
@commands.has_permissions(manage_roles=True)
async def approve(ctx, member: discord.Member):
    guild = ctx.guild

    unverified = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE)
    confirmed = discord.utils.get(guild.roles, name=CONFIRMED_ROLE)

    if confirmed in member.roles:
        await ctx.send("This user is already verified.")
        return

    await member.add_roles(confirmed)
    if unverified in member.roles:
        await member.remove_roles(unverified)

    await ctx.send(f"{member.mention} has been verified!")
    try:
        await member.send("🎉 Your NST verification is approved! Welcome aboard.")
    except:
        pass

@bot.command()
@commands.has_permissions(manage_roles=True)
async def reject(ctx, member: discord.Member, *, reason="No reason provided"):
    unverified = discord.utils.get(ctx.guild.roles, name=UNVERIFIED_ROLE)

    await ctx.send(f"{member.mention}'s verification was rejected.")
    try:
        await member.send(f"Your NST verification was rejected.\nReason: {reason}")
    except:
        pass



bot.run(token, log_handler=handler, log_level=logging.INFO)
