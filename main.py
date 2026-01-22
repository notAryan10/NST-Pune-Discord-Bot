import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import aiofiles
import uuid
from pymongo import MongoClient
from datetime import datetime


load_dotenv()
token = os.getenv("DISCORD_TOKEN")
mongo_uri = os.getenv("MONGO_URI")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BAD_WORDS = ["shit", "fuck"]
allowed_extensions = ["pdf", "png"]
YEAR_ROLES = ["Freshers", "2nd Year", "3rd Year", "4th Year"]
CURRENT_YEAR = 2026


UNVERIFIED_ROLE = "Unverified"
CONFIRMED_ROLE = "Confirmed Student"
VERIFICATION_CHANNEL = "verification-queue"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

mongo_client = MongoClient(mongo_uri)
db = mongo_client["nst_bot"]
verifications = db["verifications"]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is online and ready")

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name=UNVERIFIED_ROLE)
    if role:
        await member.add_roles(role)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    msg = message.content.lower()
    for word in BAD_WORDS:
        if word in msg:
            await message.delete()
            await message.channel.send(f"{message.author.mention} ⚠️ Please avoid inappropriate language.")
            return
    await bot.process_commands(message)


def get_current_academic_year():
    now = datetime.now()
    if now.month >= 7:
        return now.year
    else:
        return now.year - 1

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! Bot is working.")

@bot.command()
async def test(ctx, *, arg):
    await ctx.send(arg)

@bot.command()
async def add(ctx, a: int, b: int):
    await ctx.send(f"Result: {a + b}")

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

    existing = verifications.find_one({"user_id": str(user.id), "status": "pending"})
    if existing:
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
    filename = attachment.filename.lower()

    allowed_extensions = ["pdf", "png"]
    ext = filename.split(".")[-1]

    if ext not in allowed_extensions:
        await ctx.send(
            "❌ Invalid file format.\n"
            "Accepted formats: **PDF (.pdf)** or **PNG (.png)** only."
        )
        return

    queue_channel = discord.utils.get(guild.text_channels, name=VERIFICATION_CHANNEL)

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
        color=discord.Color.gold()
    )
    embed.set_footer(text="Use !approve @user or !reject @user")

    msg = await queue_channel.send(embed=embed)
    await queue_channel.send(file=await attachment.to_file())

    record = {
        "user_id": str(user.id),
        "username": str(user),
        "file_url": attachment.url,
        "file_name": attachment.filename,
        "file_type": ext,
        "status": "pending",
        "submitted_at": datetime.utcnow(),
        "reviewed_at": None,
        "reviewed_by": None,
        "reason": None,
        "queue_message_id": str(msg.id)
    }

    verifications.insert_one(record)

    await ctx.send("📨 Your document has been submitted for verification.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def approve(ctx, member: discord.Member):
    guild = ctx.guild

    record = verifications.find_one({"user_id": str(member.id), "status": "pending"})
    if not record:
        await ctx.send("No pending verification found for this user.")
        return

    unverified = discord.utils.get(guild.roles, name=UNVERIFIED_ROLE)
    confirmed = discord.utils.get(guild.roles, name=CONFIRMED_ROLE)

    await member.add_roles(confirmed)
    if unverified in member.roles:
        await member.remove_roles(unverified)

    verifications.update_one(
        {"_id": record["_id"]},
        {"$set": {
            "status": "approved",
            "reviewed_at": datetime.utcnow(),
            "reviewed_by": str(ctx.author.id)
        }}
    )

    await ctx.send(f"{member.mention} has been verified!")

    try:
        await member.send("🎉 Your NST verification is approved! Welcome aboard.")
    except:
        pass

@bot.command()
@commands.has_permissions(manage_roles=True)
async def reject(ctx, member: discord.Member, *, reason="No reason provided"):
    record = verifications.find_one({"user_id": str(member.id), "status": "pending"})
    if not record:
        await ctx.send("No pending verification found for this user.")
        return

    verifications.update_one(
        {"_id": record["_id"]},
        {"$set": {
            "status": "rejected",
            "reviewed_at": datetime.utcnow(),
            "reviewed_by": str(ctx.author.id),
            "reason": reason
        }}
    )

    await ctx.send(f"❌ {member.mention}'s verification was rejected.")

    try:
        await member.send(
            f"Your NST verification was rejected.\nReason: {reason}"
        )
    except:
        pass


@bot.command()
async def batch(ctx):
    guild = ctx.guild
    user = ctx.author

    confirmed = discord.utils.get(guild.roles, name=CONFIRMED_ROLE)

    if confirmed not in user.roles:
        await ctx.send("You must be verified before setting your batch.")
        return

    existing = db["batches"].find_one({"user_id": str(user.id)})
    if existing:
        await ctx.send(
            f"🔒 You already submitted your batch info.\n"
            f"Assigned role: **{existing['assigned_role']}**\n"
            "Contact admin if incorrect."
        )
        return

    await ctx.send("📝 Please enter your **Full Name**:")

    def check_name(m):
        return m.author == user and m.channel == ctx.channel

    try:
        name_msg = await bot.wait_for("message", timeout=60.0, check=check_name)
    except:
        await ctx.send("⏳ Timed out. Please run `!batch` again.")
        return

    full_name = name_msg.content.strip()

    await ctx.send("🔢 Now enter your **URN Number** (e.g. `2024-B-123456789B`):")

    def check_urn(m):
        return m.author == user and m.channel == ctx.channel

    try:
        urn_msg = await bot.wait_for("message", timeout=60.0, check=check_urn)
    except:
        await ctx.send("⏳ Timed out. Please run `!batch` again.")
        return

    urn = urn_msg.content.strip().upper()

    if len(urn) < 6 or not urn[:4].isdigit():
        await ctx.send("❌ Invalid URN format.\nExpected format: `2024-B-XXXXXXXX`")
        return

    admission_year = int(urn[:4])

    current_academic_year = get_current_academic_year()
    academic_year_number = current_academic_year - admission_year + 1

    year_map = {
        1: "Freshers",
        2: "2nd Year",
        3: "3rd Year",
        4: "4th Year"
    }

    if academic_year_number not in year_map:
        await ctx.send(
            "Your URN does not map to a valid academic year.\n"
            "Contact admin for manual review."
        )
        return

    role_name = year_map[academic_year_number]
    role = discord.utils.get(guild.roles, name=role_name)

    if not role:
        await ctx.send("❌ Year role not found. Contact Admin.")
        return

    await user.add_roles(role)

    db["batches"].insert_one({
        "user_id": str(user.id),
        "name": full_name,
        "urn": urn,
        "admission_year": admission_year,
        "academic_year_number": academic_year_number,
        "assigned_role": role_name,
        "submitted_at": datetime.utcnow()
    })

    await ctx.send(
        f"✅ Batch verified!\n"
        f"👤 Name: **{full_name}**\n"
        f"🎓 Admission Year: **{admission_year}**\n"
        f"📆 Current Academic Year: **{current_academic_year}**\n"
        f"📌 Assigned Role: **{role_name}**\n\n"
        "🔒 This cannot be changed. Contact Admin if incorrect."
    )

@bot.event
async def on_member_update(before, after):
    before_roles = {r.name for r in before.roles}
    after_roles = {r.name for r in after.roles}

    added_roles = after_roles - before_roles
    year_roles = set(YEAR_ROLES)

    if added_roles & year_roles:
        if before_roles & year_roles:
            new_role = list(added_roles & year_roles)[0]
            role_obj = discord.utils.get(after.guild.roles, name=new_role)
            if role_obj:
                await after.remove_roles(role_obj)

            try:
                await after.send(
                    "🔒 Year roles are locked. Contact Admin for changes.")
            except:
                pass


bot.run(token, log_handler=handler, log_level=logging.INFO)
