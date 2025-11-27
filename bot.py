import os
import random
from datetime import timedelta

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# ----------------- ENV + BASIC SETUP -----------------

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("MTQ0MzQwNzkyOTg1MTExNzU2OA.G4QdpV.MrhW5LxDBFOvxFfCIrdSz3WR3KY5z9-JxSLxO4")
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN missing hai!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # roles/members ke liye

class XtremeBot(commands.Bot):
    async def on_ready(self):
        try:
            synced = await self.tree.sync()
            print(f"🔥 Xtreme online — {len(synced)} slash commands synced ⚡")
        except Exception as e:
            print("Slash sync error:", e)

bot = XtremeBot(command_prefix="!", intents=intents)

# ----------------- WARN STORAGE (IN-MEMORY) -----------------
# warnings[(guild_id, user_id)] = count
warnings = {}

# ----------------- TIMEOUT DURATIONS -----------------

ALLOWED_DURATIONS = {
    "10s": timedelta(seconds=10),
    "1m": timedelta(minutes=1),
    "10m": timedelta(minutes=10),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
}
REMOVE_KEYS = ("remove", "off", "none")

def list_allowed_durations():
    return ", ".join(ALLOWED_DURATIONS.keys()) + ", remove"

# ----------------- ROLE / PERMISSION SAFETY -----------------

async def can_act(ctx_or_inter, target: discord.Member) -> bool:
    """Check karega ki user + bot dono is member par action le sakte hain ya nahi."""
    guild = target.guild
    me = guild.me

    if isinstance(ctx_or_inter, discord.Interaction):
        author = ctx_or_inter.user
        async def send(msg, **kw):
            if not ctx_or_inter.response.is_done():
                await ctx_or_inter.response.send_message(msg, **kw)
            else:
                await ctx_or_inter.followup.send(msg, **kw)
    else:
        author = ctx_or_inter.author
        send = ctx_or_inter.send

    # Khud par action
    if target == author:
        await send("Khud ko hi punish karega? 😅")
        return False

    # Server owner
    if target == guild.owner:
        await send("Server owner par action nahi le sakte 😶")
        return False

    # Author role < target role
    if author.top_role <= target.top_role and author != guild.owner:
        await send("Tera role usse neeche/equal hai, is par action nahi le sakta ⚠️")
        return False

    # Bot role < target role
    if me.top_role <= target.top_role:
        await send("Mera (Xtreme ka) role usse neeche hai, main uspe action nahi le sakta 😔")
        return False

    return True

# ----------------- TIMEOUT COMMON LOGIC -----------------

async def timeout_logic(ctx_or_inter, member: discord.Member, duration_key: str, reason: str, slash: bool):
    if not await can_act(ctx_or_inter, member):
        return

    async def send(msg, **kw):
        if isinstance(ctx_or_inter, discord.Interaction):
            if not ctx_or_inter.response.is_done():
                await ctx_or_inter.response.send_message(msg, **kw)
            else:
                await ctx_or_inter.followup.send(msg, **kw)
        else:
            await ctx_or_inter.send(msg, **kw)

    try:
        dk = duration_key.lower()

        if dk in REMOVE_KEYS:
            await member.edit(timed_out_until=None, reason=reason)
            msg = f"✅ {member.mention} ka timeout remove kar diya.\nReason: {reason}"
        else:
            delta = ALLOWED_DURATIONS.get(dk)
            if not delta:
                msg = f"❌ Invalid duration! Allowed: `{list_allowed_durations()}`"
            else:
                until = discord.utils.utcnow() + delta
                await member.edit(timed_out_until=until, reason=reason)
                msg = (
                    f"⏳ **Xtreme Timeout Executed**\n"
                    f"👤 User: {member.mention}\n"
                    f"⌛ Duration: `{duration_key}`\n"
                    f"📄 Reason: {reason}"
                )

        await send(msg)

    except Exception as e:
        await send(f"Timeout failed 😭 — `{e}`")

# ----------------- WARN SYSTEM -----------------

def add_warning(guild_id: int, user_id: int) -> int:
    key = (guild_id, user_id)
    warnings[key] = warnings.get(key, 0) + 1
    return warnings[key]

def get_warnings(guild_id: int, user_id: int) -> int:
    return warnings.get((guild_id, user_id), 0)

async def issue_warn(ctx_or_inter, member: discord.Member, reason: str, slash: bool):
    if not await can_act(ctx_or_inter, member):
        return

    guild = member.guild
    count = add_warning(guild.id, member.id)

    # Decide auto action
    auto_action = None
    if count == 2:
        auto_action = ("timeout", "10m")
    elif count == 3:
        auto_action = ("timeout", "1h")
    elif count == 4:
        auto_action = ("kick", None)
    elif count >= 5:
        auto_action = ("ban", None)

    # DM to user
    try:
        dm_text = (
            f"⚠️ You received a warning in **{guild.name}**.\n"
            f"Reason: {reason}\n"
            f"Total Warns: {count}"
        )
        if auto_action:
            atype, dur = auto_action
            if atype == "timeout":
                dm_text += f"\nAuto Action: Timeout `{dur}` by Xtreme."
            elif atype == "kick":
                dm_text += "\nAuto Action: Kick by Xtreme."
            elif atype == "ban":
                dm_text += "\nAuto Action: Ban by Xtreme."
        await member.send(dm_text)
    except discord.Forbidden:
        pass

    # Send in channel
    if isinstance(ctx_or_inter, discord.Interaction):
        if not ctx_or_inter.response.is_done():
            send = ctx_or_inter.response.send_message
        else:
            send = ctx_or_inter.followup.send
    else:
        send = ctx_or_inter.send

    base_msg = (
        f"⚠️ **Xtreme Warn Issued**\n"
        f"👤 User: {member.mention}\n"
        f"📄 Reason: {reason}\n"
        f"📊 Total Warns: `{count}`"
    )

    # Apply auto action
    if auto_action:
        atype, dur = auto_action
        if atype == "timeout":
            await timeout_logic(ctx_or_inter, member, dur, f"Auto timeout (warns = {count})", slash)
            extra = f"\n🚨 Auto Action: Timeout `{dur}`"
        elif atype == "kick":
            await member.kick(reason=f"Auto kick (warns = {count})")
            extra = "\n🚨 Auto Action: Kick"
        elif atype == "ban":
            await member.ban(reason=f"Auto ban (warns = {count})")
            extra = "\n🚨 Auto Action: Ban"
        await send(base_msg + extra)
    else:
        await send(base_msg)

# ----------------- KICK (PREFIX + SLASH) -----------------

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_prefix(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not await can_act(ctx, member):
        return
    await member.kick(reason=reason)
    await ctx.send(
        f"👢 **Xtreme Kick Executed**\n"
        f"👤 User: {member.mention}\n"
        f"📄 Reason: {reason}\n"
        f"👮 Mod: {ctx.author.mention}"
    )

@bot.tree.command(name="kick", description="Kick a member (Xtreme)")
@app_commands.checks.has_permissions(kick_members=True)
@app_commands.describe(member="Jisko kick karna hai", reason="Reason")
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if not await can_act(interaction, member):
        return
    await member.kick(reason=reason)
    await interaction.response.send_message(
        f"👢 **Xtreme Kick Executed**\n"
        f"👤 User: {member.mention}\n"
        f"📄 Reason: {reason}\n"
        f"👮 Mod: {interaction.user.mention}"
    )

# ----------------- BAN (PREFIX + SLASH) -----------------

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_prefix(ctx, member: discord.Member, *, reason: str = "No reason"):
    if not await can_act(ctx, member):
        return
    await member.ban(reason=reason)
    await ctx.send(
        f"🔨 **Xtreme Ban Executed**\n"
        f"👤 User: {member.mention}\n"
        f"📄 Reason: {reason}\n"
        f"👮 Mod: {ctx.author.mention}"
    )

@bot.tree.command(name="ban", description="Ban a member (Xtreme)")
@app_commands.checks.has_permissions(ban_members=True)
@app_commands.describe(member="Jisko ban karna hai", reason: "Reason")
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    if not await can_act(interaction, member):
        return
    await member.ban(reason=reason)
    await interaction.response.send_message(
        f"🔨 **Xtreme Ban Executed**\n"
        f"👤 User: {member.mention}\n"
        f"📄 Reason: {reason}\n"
        f"👮 Mod: {interaction.user.mention}"
    )

# ----------------- TIMEOUT (PREFIX + SLASH) -----------------

@bot.command(name="timeout")
@commands.has_permissions(moderate_members=True)
async def timeout_prefix(ctx, member: discord.Member, duration: str, *, reason: str = "No reason"):
    await timeout_logic(ctx, member, duration, reason, slash=False)

@bot.tree.command(name="timeout", description="Timeout / remove timeout (Xtreme)")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(
    member="Jisko timeout karna hai",
    duration="10s, 1m, 10m, 1h, 2h, remove",
    reason="Reason (optional)"
)
@app_commands.choices(duration=[
    app_commands.Choice(name="10 seconds", value="10s"),
    app_commands.Choice(name="1 minute", value="1m"),
    app_commands.Choice(name="10 minutes", value="10m"),
    app_commands.Choice(name="1 hour", value="1h"),
    app_commands.Choice(name="2 hours", value="2h"),
    app_commands.Choice(name="Remove timeout", value="remove"),
])
async def timeout_slash(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: app_commands.Choice[str],
    reason: str = "No reason"
):
    await timeout_logic(interaction, member, duration.value, reason, slash=True)

# ----------------- WARN (PREFIX + SLASH) -----------------

@bot.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn_prefix(ctx, member: discord.Member, *, reason: str = "No reason"):
    await issue_warn(ctx, member, reason, slash=False)

@bot.tree.command(name="warn", description="Warn a member (auto punish)")
@app_commands.checks.has_permissions(moderate_members=True)
@app_commands.describe(member="Jisko warn karna hai", reason="Reason")
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await issue_warn(interaction, member, reason, slash=True)

@bot.command(name="warns")
async def warns_prefix(ctx, member: discord.Member):
    count = get_warnings(ctx.guild.id, member.id)
    await ctx.send(f"{member.mention} ke total warns: **{count}**")

# ----------------- COINFLIP (PREFIX + SLASH) -----------------

@bot.command(name="coinflip")
async def coinflip_prefix(ctx):
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await ctx.send(f"🎲 Coin flipped: **{result}**")

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip_slash(interaction: discord.Interaction):
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await interaction.response.send_message(f"🎲 Coin flipped: **{result}**")

# ----------------- HELP (PREFIX + SLASH) -----------------

HELP_TEXT = (
    "🌀 **XTREME HELP MENU**\n\n"
    "⚔️ **Moderation**\n"
    "`!kick @user reason` — Kick user\n"
    "`!ban @user reason` — Ban user\n"
    "`!timeout @user 10m reason` — Timeout (10s,1m,10m,1h,2h,remove)\n"
    "`!warn @user reason` — Warn + auto punish\n"
    "`!warns @user` — Total warns\n\n"
    "🎲 **Fun**\n"
    "`!coinflip` — Heads/Tails\n"
)

@bot.command(name="help")
async def help_prefix(ctx):
    await ctx.send(HELP_TEXT)

@bot.tree.command(name="help", description="Show Xtreme help menu")
async def help_slash(interaction: discord.Interaction):
    await interaction.response.send_message(HELP_TEXT)

# ----------------- RUN BOT -----------------

bot.run(DISCORD_BOT_TOKEN)
