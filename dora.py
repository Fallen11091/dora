import discord
from discord.ext import commands
from discord import app_commands
import os
import re
import json
import time
import asyncio
import tempfile
from collections import defaultdict
from typing import Union
from datetime import datetime, timedelta, timezone

PH_TIMEZONE = timezone(timedelta(hours=8))

def ph_now():
    return datetime.now(PH_TIMEZONE)


TOKEN = "MTQ4ODM0NjUwMTI5Mjc1NzEzNA.GdTTbO.ngPOOPucQupMm8zDBcEYfyt6511w5JlC73yRmc"

OWNER_ID = 1468857011570479177
owner_user = None

EMBED_COLOR = 0x2b2d31
BLOCK_INVITE_CODE = "WG8RKfYts"

CONFIG_FILE = "config.json"
POINTS_FILE = "points.json"
LOGS_FILE = "ps_logs.json"
CLAIMS_FILE = "claim_messages.json"
BACKUPS_FILE = "mt.json"
SNIPES_FILE = "snipes.json"

INV_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/([A-Za-z0-9]+)",
    re.I
)

ROLE_REACTION_EMOJI_RE = re.compile(r"<(a?):([A-Za-z0-9_]+):(\d+)>")

_file_locks = defaultdict(asyncio.Lock)


def _load_json_sync(filename: str, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _atomic_write_sync(filename: str, data_obj):
    dir_ = os.path.dirname(filename) or "."
    payload = json.dumps(data_obj, indent=4, ensure_ascii=False)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_, encoding="utf-8") as tf:
        tf.write(payload)
        tmp = tf.name
    os.replace(tmp, filename)


async def save_json(filename: str, data_obj):
    async with _file_locks[filename]:
        _atomic_write_sync(filename, data_obj)


def load_points_fresh():
    return _load_json_sync(POINTS_FILE, {})


config = _load_json_sync(CONFIG_FILE, {"guilds": {}})
user_points = _load_json_sync(POINTS_FILE, {})
ps_logs = _load_json_sync(LOGS_FILE, {})
claim_messages = _load_json_sync(CLAIMS_FILE, {})
server_backups = _load_json_sync(BACKUPS_FILE, {})
persistent_snipes = _load_json_sync(SNIPES_FILE, {})

GUILD_DEFAULTS = {
    "ps_prefix": "ps ",
    "util_prefix": ",",
    "log_channel_id": None,
    "partnership_channel_id": None,
    "ps_manager_role_id": None,
    "partner_role_id": None,
    "automod_enabled": False,
    "antilink_enabled": False,
    "antispam_enabled": False,
    "autoresponder_enabled": False,
    "autoresponses": {},
    "autoreact_users": {},
    "automod_log_channel_id": None,
    "automod_whitelist_role_ids": [],
    "automod_whitelist_user_ids": [],
    "welcome_channel_id": None,
    "leave_channel_id": None,
    "welcome_embed_text": "welcome {user} to {server_name} wag ka mahiyan mag lapag",
    "leave_embed_text": "bye hanggang sa muling pag kikita kapatid {user} paalam",
    "welcome_message_channel_id": None,
    "leave_message_channel_id": None,
    "welcome_message_text": "welcome pokpok {user}",
    "leave_message_text": "paalam {user}",
    "anti_channel_create": False,
    "anti_role_create": False,
    "anti_role_delete": False,
    "anti_webhook_create": False,
    "anti_bot_add": False,
    "anti_channel_delete": False,
    "anti_channel_rename": False,
    "anti_server_rename": False,
    "anti_role_escalation": False,
    "anti_mass_ban": False,
    "anti_mass_kick": False,
    "anti_punish": "ban",
    "role_reactions": [],
    "anti_interaction_spam_limit": 6,
    "anti_interaction_spam_window": 8,
    "server_ad": None,
}

def get_guild_config(guild_id: int):
    gid = str(guild_id)
    guilds = config.setdefault("guilds", {})

    if gid not in guilds:
        guilds[gid] = GUILD_DEFAULTS.copy()
        _atomic_write_sync(CONFIG_FILE, config)

    guild_cfg = guilds[gid]

    defaults = GUILD_DEFAULTS.copy()

    changed = False
    for key, value in defaults.items():
        if key not in guild_cfg:
            guild_cfg[key] = value
            changed = True

    if changed:
        _atomic_write_sync(CONFIG_FILE, config)

    return guild_cfg

def save_config():
    _atomic_write_sync(CONFIG_FILE, config)

def parse_timeout_duration(duration: str):
    if not duration:
        return None

    duration = duration.strip().lower()

    if len(duration) < 2:
        return None

    unit = duration[-1]
    value_part = duration[:-1]

    if not value_part.isdigit():
        return None

    value = int(value_part)

    if value <= 0:
        return None

    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)

    return None

def format_duration_text(duration: str) -> str:
    duration = duration.strip().lower()
    value = int(duration[:-1])
    unit = duration[-1]

    if unit == "m":
        return f"{value} minute" if value == 1 else f"{value} minutes"
    if unit == "h":
        return f"{value} hour" if value == 1 else f"{value} hours"
    if unit == "d":
        return f"{value} day" if value == 1 else f"{value} days"

    return duration


def mod_footer_text(guild: discord.Guild) -> str:
    now_text = ph_now().strftime("%I:%M %p")
    return f"{guild.name} | Today at : {now_text}"


def get_target_thumbnail(member: discord.Member = None, user: discord.User = None) -> str | None:
    if member:
        return member.display_avatar.url
    if user:
        return user.display_avatar.url
    return None


def build_mod_embed(
    guild: discord.Guild,
    action_text: str,
    target_text: str,
    target_id: int,
    moderator: discord.abc.User,
    color: int,
    reason: str = None,
    duration_text: str = None,
    thumb_url: str = None
):
    emb = discord.Embed(color=color)

    emb.add_field(name="User", value=target_text, inline=False)
    emb.add_field(name="ID", value=f"`{target_id}`", inline=False)

    if duration_text:
        emb.add_field(name="Duration", value=f"`{duration_text}`", inline=False)

    emb.add_field(name="Moderator", value=moderator.mention, inline=False)

    if reason:
        emb.add_field(name="Reason", value=f"`{reason}`", inline=False)

    if thumb_url:
        emb.set_thumbnail(url=thumb_url)

    emb.set_author(name=action_text)
    emb.set_footer(text=mod_footer_text(guild), icon_url=guild.icon.url if guild.icon else moderator.display_avatar.url)

    return emb


def resolve_member_from_input(ctx, raw_target: str):
    raw_target = raw_target.strip()

    mention_match = re.fullmatch(r"<@!?(\d+)>", raw_target)
    if mention_match:
        user_id = int(mention_match.group(1))
        return ctx.guild.get_member(user_id)

    if raw_target.isdigit():
        return ctx.guild.get_member(int(raw_target))

    return None

async def punish_user(guild, user_id, reason):
    cfg = get_guild_config(guild.id)
    action = cfg.get("anti_punish", "ban")

    try:
        member = guild.get_member(user_id)
        if not member:
            return

        if is_automod_whitelisted(member, cfg):
            return

        me = guild.me or guild.get_member(bot.user.id)
        if not me:
            return

        if member == guild.owner:
            return

        if member.top_role >= me.top_role:
            return

        if action == "ban":
            await guild.ban(member, reason=reason)
        elif action == "kick":
            await guild.kick(member, reason=reason)

    except Exception:
        pass

async def send_anti_nuke_log(guild, title, user, reason):
    cfg = get_guild_config(guild.id)
    log_channel_id = cfg.get("automod_log_channel_id")

    if not log_channel_id:
        return

    ch = guild.get_channel(int(log_channel_id))
    if not ch:
        return

    emb = discord.Embed(
        title=title,
        description=f"{user.mention}\n`{user.id}`\n{reason}",
        color=0xed4245
    )

    if hasattr(user, "display_avatar"):
        emb.set_thumbnail(url=user.display_avatar.url)

    try:
        await fallen_safe_send(ch, embed=emb)
    except Exception:
        pass


def serialize_role(role: discord.Role):
    return {
        "name": role.name,
        "permissions": role.permissions.value,
        "color": role.color.value,
        "hoist": role.hoist,
        "mentionable": role.mentionable,
        "position": role.position
    }

def serialize_overwrites(channel: discord.abc.GuildChannel):
    data = []
    for target, overwrite in channel.overwrites.items():
        allow, deny = overwrite.pair()

        if isinstance(target, discord.Role):
            data.append({
                "type": "role",
                "name": target.name,
                "id": target.id,
                "allow": allow.value,
                "deny": deny.value
            })
        elif isinstance(target, discord.Member):
            data.append({
                "type": "member",
                "id": target.id,
                "allow": allow.value,
                "deny": deny.value
            })

    return data


def serialize_category(category: discord.CategoryChannel):
    return {
        "name": category.name,
        "position": category.position,
        "overwrites": serialize_overwrites(category)
    }


def serialize_channel(channel: discord.abc.GuildChannel):
    base = {
        "name": channel.name,
        "position": channel.position,
        "category": channel.category.name if channel.category else None,
        "overwrites": serialize_overwrites(channel)
    }

    if isinstance(channel, discord.TextChannel):
        base.update({
            "type": "text",
            "topic": channel.topic,
            "nsfw": channel.nsfw,
            "slowmode_delay": channel.slowmode_delay
        })
    elif isinstance(channel, discord.VoiceChannel):
        base.update({
            "type": "voice",
            "bitrate": channel.bitrate,
            "user_limit": channel.user_limit
        })
    else:
        return None

    return base

async def restore_deleted_role(guild: discord.Guild, role: discord.Role):
    try:
        me = guild.me or guild.get_member(bot.user.id)
        if not me or not me.guild_permissions.manage_roles:
            return

        new_role = await guild.create_role(
            name=role.name,
            permissions=role.permissions,
            colour=role.color,
            hoist=role.hoist,
            mentionable=role.mentionable,
            reason="Anti role delete restore"
        )

        try:
            await new_role.edit(position=role.position)
        except Exception:
            pass

    except Exception:
        pass


async def restore_deleted_channel(guild: discord.Guild, channel):
    try:
        me = guild.me or guild.get_member(bot.user.id)
        if not me or not me.guild_permissions.manage_channels:
            return

        category = None
        if channel.category:
            category = discord.utils.get(guild.categories, name=channel.category.name)

        overwrites = channel.overwrites

        if isinstance(channel, discord.TextChannel):
            await guild.create_text_channel(
                name=channel.name,
                category=category,
                topic=channel.topic,
                nsfw=channel.nsfw,
                slowmode_delay=channel.slowmode_delay,
                overwrites=overwrites,
                reason="Anti channel delete restore"
            )

        elif isinstance(channel, discord.VoiceChannel):
            await guild.create_voice_channel(
                name=channel.name,
                category=category,
                bitrate=channel.bitrate,
                user_limit=channel.user_limit,
                overwrites=overwrites,
                reason="Anti channel delete restore"
            )

    except Exception:
        pass

def build_overwrites(guild: discord.Guild, overwrites_data, role_map):
    overwrites = {}

    for ow in overwrites_data:
        target = None

        if ow["type"] == "role":
            target = role_map.get(ow["name"])
            if not target:
                target = discord.utils.get(guild.roles, name=ow["name"])

        elif ow["type"] == "member":
            target = guild.get_member(int(ow["id"]))

        if not target:
            continue

        overwrites[target] = discord.PermissionOverwrite.from_pair(
            discord.Permissions(ow["allow"]),
            discord.Permissions(ow["deny"])
        )

    return overwrites


async def backup_guild_structure(guild: discord.Guild, backup_name: str):
    roles = []
    for role in reversed(guild.roles):
        if role.is_default() or role.managed:
            continue
        roles.append(serialize_role(role))

    categories = []
    for category in guild.categories:
        categories.append(serialize_category(category))

    channels = []
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            continue
        data = serialize_channel(channel)
        if data:
            channels.append(data)

    server_backups[backup_name] = {
        "guild_name": guild.name,
        "guild_id": guild.id,
        "created_at": ph_now().strftime("%Y-%m-%d %H:%M:%S"),
        "roles": roles,
        "categories": categories,
        "channels": channels
    }

    await save_json(BACKUPS_FILE, server_backups)


def find_existing_role(guild: discord.Guild, role_data):
    return discord.utils.get(guild.roles, name=role_data["name"])


async def restore_roles(guild: discord.Guild, roles_data):
    role_map = {}

    for role_data in roles_data:
        existing = find_existing_role(guild, role_data)

        if existing:
            role_map[role_data["name"]] = existing
            continue

        try:
            new_role = await guild.create_role(
                name=role_data["name"],
                permissions=discord.Permissions(role_data["permissions"]),
                colour=discord.Colour(role_data["color"]),
                hoist=role_data["hoist"],
                mentionable=role_data["mentionable"],
                reason="Server backup restore"
            )
            role_map[role_data["name"]] = new_role
        except Exception:
            pass

    desired_positions = {}
    for role_data in roles_data:
        role_obj = role_map.get(role_data["name"])
        if role_obj:
            desired_positions[role_obj] = role_data["position"]

    if desired_positions:
        try:
            await guild.edit_role_positions(positions=desired_positions)
        except Exception:
            pass

    return role_map


async def restore_categories(guild: discord.Guild, categories_data, role_map):
    category_map = {}

    for cat_data in categories_data:
        existing = discord.utils.get(guild.categories, name=cat_data["name"])

        if existing:
            category_map[cat_data["name"]] = existing
            continue

        overwrites = build_overwrites(guild, cat_data.get("overwrites", []), role_map)

        try:
            new_cat = await guild.create_category(
                name=cat_data["name"],
                overwrites=overwrites,
                reason="Server backup restore"
            )
            category_map[cat_data["name"]] = new_cat
        except Exception:
            pass

    for cat_data in categories_data:
        category = category_map.get(cat_data["name"])
        if category:
            try:
                await category.edit(position=cat_data["position"])
            except Exception:
                pass

    return category_map


async def restore_channels(guild: discord.Guild, channels_data, category_map, role_map):
    for ch_data in channels_data:
        category = category_map.get(ch_data["category"]) if ch_data.get("category") else None
        overwrites = build_overwrites(guild, ch_data.get("overwrites", []), role_map)

        existing = None
        if ch_data["type"] == "text":
            existing = discord.utils.get(guild.text_channels, name=ch_data["name"])
        elif ch_data["type"] == "voice":
            existing = discord.utils.get(guild.voice_channels, name=ch_data["name"])

        if existing:
            try:
                await existing.edit(
                    category=category,
                    position=ch_data["position"],
                    overwrites=overwrites
                )
            except Exception:
                pass
            continue

        try:
            if ch_data["type"] == "text":
                await guild.create_text_channel(
                    name=ch_data["name"],
                    category=category,
                    topic=ch_data.get("topic"),
                    nsfw=ch_data.get("nsfw", False),
                    slowmode_delay=ch_data.get("slowmode_delay", 0),
                    overwrites=overwrites,
                    reason="Server backup restore"
                )

            elif ch_data["type"] == "voice":
                await guild.create_voice_channel(
                    name=ch_data["name"],
                    category=category,
                    bitrate=ch_data.get("bitrate", 64000),
                    user_limit=ch_data.get("user_limit", 0),
                    overwrites=overwrites,
                    reason="Server backup restore"
                )
        except Exception:
            pass

def clean_expired_claims(max_age_seconds: int = 86400):
    now = time.time()
    expired = []

    for mid, data in list(claim_messages.items()):
        created = data.get("created_at")
        if created and (now - float(created)) > max_age_seconds:
            expired.append(mid)

    for mid in expired:
        claim_messages.pop(mid, None)

    if expired:
        _atomic_write_sync(CLAIMS_FILE, claim_messages)


active_states = {}
cooldown_ts = defaultdict(float)


def on_cd(user_id: int, secs: int = 4) -> bool:
    now = time.time()
    if now - cooldown_ts[user_id] < secs:
        return True
    cooldown_ts[user_id] = now
    return False


claim_view = None
bot_ref = {"bot": None}
bot_start_time = time.time()

interaction_spam_cache = defaultdict(list)

afk_users = {}
snipe_cache = defaultdict(list)

for channel_id, items in persistent_snipes.items():
    try:
        snipe_cache[int(channel_id)] = items
    except Exception:
        pass
spam_cache = defaultdict(list)
anti_cache = defaultdict(list)
nuke_tracker = defaultdict(list)
afk_notify_cache = {}
sticky_cooldown = {}
sticky_messages = {}
fallen_send_queue = asyncio.Queue()
fallen_sender_task = None
fallen_channel_cooldowns = {}
fallen_role_action_cooldowns = {}
autoreact_cooldowns = {}

URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)

async def fallen_safe_send(
    channel,
    content=None,
    embed=None,
    view=None,
    reference=None,
    delete_after=None
):
    await fallen_send_queue.put({
        "channel": channel,
        "content": content,
        "embed": embed,
        "view": view,
        "reference": reference,
        "delete_after": delete_after
    })

async def handle_interaction_spam(interaction: discord.Interaction):
    if not interaction.guild or not interaction.user:
        return False

    if getattr(interaction.user, "bot", False):
        return False

    cfg = get_guild_config(interaction.guild.id)

    if not cfg.get("anti_interaction_spam", False):
        return False

    if is_automod_whitelisted(interaction.user, cfg):
        return False

    limit = int(cfg.get("anti_interaction_spam_limit", 6))
    window = int(cfg.get("anti_interaction_spam_window", 8))

    key = (interaction.guild.id, interaction.user.id)
    now = time.time()

    interaction_spam_cache[key].append(now)
    interaction_spam_cache[key] = [t for t in interaction_spam_cache[key] if now - t <= window]

    count = len(interaction_spam_cache[key])

    if count < limit:
        return False

    interaction_spam_cache[key].clear()

    try:
        await send_interaction_spam_log(
            interaction.guild,
            interaction.user,
            count,
            f"{window}s"
        )
    except Exception:
        pass

    try:
        await punish_user(
            interaction.guild,
            interaction.user.id,
            f"Anti: interaction spam ({count} in {window}s)"
        )
    except Exception:
        pass

    return True

#  interaction spam
async def send_interaction_spam_log(guild, user, count, window_text):
    try:
        cfg = get_guild_config(guild.id)
        log_channel_id = cfg.get("automod_log_channel_id")
        if not log_channel_id:
            return

        log_channel = guild.get_channel(int(log_channel_id))
        if not log_channel:
            return

        emb = discord.Embed(
            title="♰ Anti Interaction Spam",
            description=(
                f"`❌` interaction spam detected\n"
                f"`👤` user: {user.mention}\n"
                f"`🆔` id: `{user.id}`\n"
                f"`🔄` count: `{count}` in `{window_text}`"
            ),
            color=0xed4245
        )

        await fallen_safe_send(log_channel, embed=emb)
    except Exception:
        pass


async def fallen_sender_loop():
    global fallen_channel_cooldowns

    while True:
        job = await fallen_send_queue.get()

        try:
            channel = job["channel"]
            channel_id = channel.id
            now = time.time()

            last = fallen_channel_cooldowns.get(channel_id, 0)
            wait_time = 0.9 - (now - last)

            if wait_time > 0:
                await asyncio.sleep(wait_time)

            sent = None

            try:
                sent = await channel.send(
                    content=job["content"],
                    embed=job["embed"],
                    view=job["view"],
                    reference=job["reference"]
                )
            except discord.HTTPException as e:
                if e.status == 429:
                    await asyncio.sleep(3)
                else:
                    pass
            except Exception:
                pass

            if sent:
                fallen_channel_cooldowns[channel_id] = time.time()

                if job["delete_after"]:
                    async def delayed_delete(message, delay):
                        try:
                            await asyncio.sleep(delay)
                            await message.delete()
                        except Exception:
                            pass

                    asyncio.create_task(delayed_delete(sent, job["delete_after"]))

        except Exception:
            pass
        finally:
            fallen_send_queue.task_done()

async def fallen_safe_add_role(member: discord.Member, role: discord.Role, reason=None):
    key = (member.guild.id, member.id, role.id, "add")
    now = time.time()
    last = fallen_role_action_cooldowns.get(key, 0)

    wait_time = 1.5 - (now - last)
    if wait_time > 0:
        await asyncio.sleep(wait_time)

    for attempt in range(3):
        try:
            await member.add_roles(role, reason=reason)
            fallen_role_action_cooldowns[key] = time.time()
            return True
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(3 + attempt)
                continue
            return False
        except Exception:
            return False

    return False


async def fallen_safe_remove_role(member: discord.Member, role: discord.Role, reason=None):
    key = (member.guild.id, member.id, role.id, "remove")
    now = time.time()
    last = fallen_role_action_cooldowns.get(key, 0)

    wait_time = 1.5 - (now - last)
    if wait_time > 0:
        await asyncio.sleep(wait_time)

    for attempt in range(3):
        try:
            await member.remove_roles(role, reason=reason)
            fallen_role_action_cooldowns[key] = time.time()
            return True
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(3 + attempt)
                continue
            return False
        except Exception:
            return False

    return False

def format_wc_text(template: str, member: discord.Member) -> str:
    return (
        template.replace("{user}", member.mention)
        .replace("{username}", member.name)
        .replace("{server}", member.guild.name)
        .replace("{server_name}", member.guild.name)
        .replace("{count}", str(member.guild.member_count))
    )

def normalize_snipes_cache():
    changed = False

    for channel_id, items in list(persistent_snipes.items()):
        if not isinstance(items, list):
            persistent_snipes[channel_id] = []
            changed = True
            continue

        if len(items) > 10:
            persistent_snipes[channel_id] = items[:10]
            changed = True

    return changed

def build_welcome_embed(member: discord.Member, text: str):
    emb = discord.Embed(
        description=text,
        color=0x57f287
    )

    emb.set_thumbnail(url=member.display_avatar.url)

    now = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"{member.guild.member_count} | Today at {now}",
        icon_url=member.guild.icon.url if member.guild.icon else member.display_avatar.url
    )

    return emb


def build_leave_embed(member: discord.Member, text: str):
    emb = discord.Embed(
        description=text,
        color=0xed4245
    )

    emb.set_thumbnail(url=member.display_avatar.url)

    now = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"{member.guild.member_count} | Today at {now}",
        icon_url=member.guild.icon.url if member.guild.icon else member.display_avatar.url
    )

    return emb


def build_gray_message_embed(text: str):
    return discord.Embed(
        description=text,
        color=EMBED_COLOR
    )

def is_automod_whitelisted(member: discord.Member, guild_cfg: dict) -> bool:
    wl_roles = [int(rid) for rid in guild_cfg.get("automod_whitelist_role_ids", [])]
    wl_users = [int(uid) for uid in guild_cfg.get("automod_whitelist_user_ids", [])]

    if member.id in wl_users:
        return True

    if any(role.id in wl_roles for role in member.roles):
        return True

    return False

async def send_automod_log(
    guild: discord.Guild,
    guild_cfg: dict,
    title: str,
    member: discord.Member,
    reason: str,
    content: str = None
):
    channel_id = guild_cfg.get("automod_log_channel_id")
    if not channel_id:
        return

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return

    emb = discord.Embed(
        title=title,
        description=f"{member.mention}\n`{member.id}`\n{reason}",
        color=0xed4245
    )

    if content:
        emb.add_field(name="Content", value=content[:1000], inline=False)

    emb.set_thumbnail(url=member.display_avatar.url)

    try:
        await fallen_safe_send(channel, embed=emb)
    except Exception:
        pass

async def get_or_create_log_channel(guild: discord.Guild):
    guild_cfg = get_guild_config(guild.id)
    log_id = guild_cfg.get("log_channel_id")

    if log_id:
        ch = guild.get_channel(int(log_id))
        if ch:
            return ch

    me = guild.me
    if not me or not me.guild_permissions.manage_channels:
        return None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True),
    }

    new_channel = await guild.create_text_channel("ps-logs", overwrites=overwrites)
    guild_cfg["log_channel_id"] = new_channel.id
    save_config()
    return new_channel


async def log_partnership(
    partner: discord.Member,
    server_name: str,
    role_given: discord.Role | None,
    ps_manager: discord.Member
):
    guild = partner.guild
    log_channel = await get_or_create_log_channel(guild)
    if not log_channel:
        return

    emb = discord.Embed(title="Partnership Logs", color=EMBED_COLOR)

    if owner_user:
        emb.set_author(name=str(owner_user), icon_url=owner_user.display_avatar.url)

    emb.set_thumbnail(url=partner.display_avatar.url)
    emb.add_field(name="PS Manager", value=ps_manager.mention, inline=True)
    emb.add_field(name="Partner", value=partner.mention, inline=True)
    emb.add_field(name="Partner Server", value=f"**{server_name}**", inline=False)
    emb.add_field(name="Role Given", value=role_given.mention if role_given else "None", inline=True)

    guild_icon = guild.icon.url if guild.icon else bot.user.display_avatar.url
    emb.set_footer(text="Developed by fallen", icon_url=guild_icon)

    await fallen_safe_send(log_channel, embed=emb)


class ClaimRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
    label="PARTNERS",
    style=discord.ButtonStyle.secondary,
    custom_id="ps_claim_ally"
)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        data = claim_messages.get(msg_id)

        if not data:
            return await interaction.response.send_message(
                "Claim data not found (old message). Please redo `ps` process.",
                ephemeral=True
            )

        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Guild not found.", ephemeral=True)

        guild_cfg = get_guild_config(guild.id)
        partner_role_id = guild_cfg.get("partner_role_id")

        partner_id = int(data["partner_id"])
        server_name = data.get("server_name", "Unknown Server")

        partner = guild.get_member(partner_id)
        role = guild.get_role(int(partner_role_id)) if partner_role_id else None

        if not partner:
            return await interaction.response.send_message("Partner not found in this server", ephemeral=True)

        if not role:
            return await interaction.response.send_message("Role not found. Run `ps setup` first", ephemeral=True)

        me = guild.me or guild.get_member(interaction.client.user.id)
        if not me or not me.guild_permissions.manage_roles:
            return await interaction.response.send_message("i need **Manage Roles** permission.", ephemeral=True)

        if role >= me.top_role:
            return await interaction.response.send_message(
                "i can't assign that role move my bot role above the partner role",
                ephemeral=True
            )

        try:
            await partner.add_roles(role, reason="Role claimed (Partnership)")

            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

            await interaction.response.edit_message(view=self)
            await fallen_safe_send(
                interaction.channel,
                content=f"thankyou! {partner.mention} {role.mention} ^^"
            )

            gid = str(guild.id)
            manager_id = str(interaction.user.id)

            if gid not in ps_logs:
                ps_logs[gid] = {}
            if manager_id not in ps_logs[gid]:
                ps_logs[gid][manager_id] = []

            ps_logs[gid][manager_id].append({
                "partner_name": str(partner),
                "partner_id": partner.id,
                "date": ph_now().strftime("%Y-%m-%d %H:%M:%S"),
                "server_name": server_name
            })
            await save_json(LOGS_FILE, ps_logs)

            await log_partnership(partner, server_name, role, interaction.user)

            claim_messages.pop(msg_id, None)
            await save_json(CLAIMS_FILE, claim_messages)

        except Exception as e:
            try:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)
            except Exception:
                pass


def normalize_role_reaction_emoji(raw: str) -> str:
    raw = str(raw).strip()
    m = ROLE_REACTION_EMOJI_RE.fullmatch(raw)
    if m:
        animated, name, emoji_id = m.groups()
        return f"<{'a' if animated else ''}:{name}:{emoji_id}>"
    return raw


def get_reaction_object(bot: commands.Bot, emoji_key: str):
    m = ROLE_REACTION_EMOJI_RE.fullmatch(str(emoji_key))
    if not m:
        return emoji_key

    animated, name, emoji_id = m.groups()
    emoji_id = int(emoji_id)

    found = discord.utils.get(bot.emojis, id=emoji_id)
    if found:
        return found

    return discord.PartialEmoji(
        name=name,
        animated=bool(animated),
        id=emoji_id
    )


def reaction_emoji_matches(stored_emoji: str, payload_emoji) -> bool:
    stored_emoji = str(stored_emoji).strip()

    m = ROLE_REACTION_EMOJI_RE.fullmatch(stored_emoji)
    if m:
        return getattr(payload_emoji, "id", None) == int(m.group(3))

    return str(payload_emoji) == stored_emoji


def get_role_reaction_entry(guild_cfg: dict, message_id: int, emoji) -> dict | None:
    for entry in guild_cfg.get("role_reactions", []):
        if int(entry.get("message_id", 0)) == int(message_id) and reaction_emoji_matches(entry.get("emoji", ""), emoji):
            return entry
    return None

class PSBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.claim_view = None
        self.rpc_task = None

    async def setup_hook(self):
        self.claim_view = ClaimRoleView()
        self.add_view(self.claim_view)
        await self.tree.sync()

intents = discord.Intents.all()

def get_prefix(bot, message):
    if not message.guild:
        return ["ps ", ",", ", "]

    cfg = get_guild_config(message.guild.id)

    ps_prefix = str(cfg.get("ps_prefix", "ps ")).strip()
    util_prefix = str(cfg.get("util_prefix", ",")).strip()

    if not ps_prefix:
        ps_prefix = "ps"

    if not util_prefix:
        util_prefix = ","

    return [
        ps_prefix + " ",
        util_prefix,
        util_prefix + " "
    ]


bot = PSBot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=None,
    case_insensitive=True
)

bot_ref["bot"] = bot


RPC_GUILD_ID = 1462133467436417068

async def update_rpc():
    await bot.wait_until_ready()
    state = 0

    while not bot.is_closed():
        guild = bot.get_guild(RPC_GUILD_ID)

        if guild:
            server_name = guild.name
            m_count = guild.member_count or 0
        else:
            server_name = "MORTEM"
            m_count = 0

        stream_text = f"{server_name} • {m_count}"

        try:
            if state == 0:
                act = discord.Streaming(
                    name=stream_text,
                    url="https://www.twitch.tv/discord"
                )
            elif state == 1:
                act = discord.Activity(
                    type=discord.ActivityType.watching,
                    name="pinaypie.com"
                )
            elif state == 2:
                act = discord.CustomActivity(name=".gg/trinity")
            else:
                act = discord.CustomActivity(name="-help")

            await bot.change_presence(activity=act)

            state += 1
            if state > 3:
                state = 0

        except Exception as e:
            print(f"rpc error: {e}")

        await asyncio.sleep(30)


async def force_status_update(guild):
    if not guild or guild.id != RPC_GUILD_ID:
        return

    server_name = guild.name
    m_count = guild.member_count or 0
    stream_text = f"{server_name} • {m_count}"

    try:
        curr = guild.me.activity if guild.me else None

        if isinstance(curr, discord.Streaming):
            new_act = discord.Streaming(
                name=stream_text,
                url="https://www.twitch.tv/discord"
            )
        elif isinstance(curr, discord.Activity) and curr.type == discord.ActivityType.watching:
            new_act = discord.Activity(
                type=discord.ActivityType.watching,
                name="pinaypie.com"
            )
        elif isinstance(curr, discord.CustomActivity):
            current_name = getattr(curr, "name", "") or ""
            if current_name == "fallen ama ko":
                new_act = discord.CustomActivity(name=".gg/trinity")
            else:
                new_act = discord.CustomActivity(name="-help")
        else:
            new_act = discord.Streaming(
                name=stream_text,
                url="https://www.twitch.tv/discord"
            )

        await bot.change_presence(activity=new_act)

    except Exception as e:
        print(f"force status error: {e}")


@bot.event
async def on_member_join(member):
    await force_status_update(member.guild)

    cfg = get_guild_config(member.guild.id)

    if member.bot and cfg.get("anti_bot_add"):
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                user = entry.user

                if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                    return

                await punish_user(member.guild, user.id, "Anti: unauthorized bot add")
                break
        except Exception:
            pass

        try:
            await member.kick(reason="Anti bot add")
        except Exception:
            pass
        return

    welcome_channel_id = cfg.get("welcome_channel_id")
    if welcome_channel_id:
        channel = member.guild.get_channel(int(welcome_channel_id))
        if channel:
            text = format_wc_text(
                cfg.get("welcome_embed_text", "welcome {user} to {server_name} wag ka mahiyan mag lapag"),
                member
            )
            emb = build_welcome_embed(member, text)

            try:
                await fallen_safe_send(channel, embed=emb)
            except Exception:
                pass

    welcome_message_channel_id = cfg.get("welcome_message_channel_id")
    if welcome_message_channel_id:
        msg_channel = member.guild.get_channel(int(welcome_message_channel_id))
        if msg_channel:
            text = format_wc_text(
                cfg.get("welcome_message_text", "welcome pokpok {user}"),
                member
            )
            emb = build_gray_message_embed(text)

            try:
                await fallen_safe_send(msg_channel, embed=emb)
            except Exception:
                pass
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None:
        return

    if bot.user and payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = payload.member or guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    cfg = get_guild_config(guild.id)
    entry = get_role_reaction_entry(cfg, payload.message_id, payload.emoji)

    if not entry:
        return

    role = guild.get_role(int(entry["role_id"]))
    if not role:
        return

    me = guild.me or guild.get_member(bot.user.id)
    if not me or not me.guild_permissions.manage_roles:
        return

    if role >= me.top_role:
        return

    try:
        await member.add_roles(role, reason="Reaction role add")
    except Exception:
        pass


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None:
        return

    if bot.user and payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    cfg = get_guild_config(guild.id)
    entry = get_role_reaction_entry(cfg, payload.message_id, payload.emoji)

    if not entry:
        return

    role = guild.get_role(int(entry["role_id"]))
    if not role:
        return

    me = guild.me or guild.get_member(bot.user.id)
    if not me or not me.guild_permissions.manage_roles:
        return

    if role >= me.top_role:
        return

    try:
        await member.remove_roles(role, reason="Reaction role remove")
    except Exception:
        pass

@bot.event
async def on_ready():
    global owner_user
    global fallen_sender_task

    owner_user = bot.get_user(OWNER_ID)
    if owner_user is None:
        try:
            owner_user = await bot.fetch_user(OWNER_ID)
        except Exception:
            owner_user = None

    clean_expired_claims()

    if normalize_snipes_cache():
        await save_json(SNIPES_FILE, persistent_snipes)

    print(f"Connected: {bot.user}")

    if bot.rpc_task is None or bot.rpc_task.done():
        bot.rpc_task = bot.loop.create_task(update_rpc())

    if fallen_sender_task is None or fallen_sender_task.done():
        fallen_sender_task = bot.loop.create_task(fallen_sender_loop())

@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild:
        return

    if message.author.bot:
        return

    data = {
        "author_name": str(message.author),
        "author_id": message.author.id,
        "avatar": message.author.display_avatar.url,
        "content": message.content or None,
        "attachments": [a.url for a in message.attachments] if message.attachments else [],
        "stickers": [s.url for s in message.stickers] if message.stickers else [],
        "created_at": ph_now().strftime("%I:%M %p")
    }

    cid = message.channel.id
    snipe_cache[cid].insert(0, data)

    if len(snipe_cache[cid]) > 10:
        snipe_cache[cid].pop()

    persistent_snipes[str(cid)] = snipe_cache[cid]
    await save_json(SNIPES_FILE, persistent_snipes)

@bot.event
async def on_guild_channel_create(channel):
    cfg = get_guild_config(channel.guild.id)

    if cfg.get("anti_channel_create"):
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
                user = entry.user

                if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                    break

                await send_anti_nuke_log(
                    channel.guild,
                    "Anti Channel Create",
                    user,
                    f"Created channel: {channel.mention} (`{channel.name}`)"
                )

                try:
                    await channel.delete(reason="Anti channel create")
                except Exception:
                    pass

                await punish_user(channel.guild, user.id, "Anti: channel create detected")
                break
        except Exception:
            pass

    if not isinstance(channel, discord.TextChannel):
        return

    name = channel.name.lower()

    if "ticket-" not in name:
        return

    await asyncio.sleep(6)

    try:
        me = channel.guild.me or channel.guild.get_member(bot.user.id)
        if not me:
            return

        perms = channel.permissions_for(me)
        if not perms.view_channel or not perms.send_messages:
            return

        cfg = get_guild_config(channel.guild.id)
        server_ad = cfg.get("server_ad")

        if not server_ad:
            return

        await fallen_safe_send(channel, content=server_ad)
        await asyncio.sleep(2)
        await fallen_safe_send(
            channel,
            content="> -# Hello! please post our ad on your server, then drop your server ad or link here so I can post it too!"
        )

    except Exception as e:
        print(f"ticket ad error: {e}")


@bot.event
async def on_guild_channel_delete(channel):
    cfg = get_guild_config(channel.guild.id)

    if not cfg.get("anti_channel_delete"):
        return

    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            user = entry.user

            if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                return

            await send_anti_nuke_log(
                channel.guild,
                "Anti Channel Delete",
                user,
                f"Deleted channel: `{channel.name}`"
            )

            await restore_deleted_channel(channel.guild, channel)
            await punish_user(channel.guild, user.id, "Anti: channel delete detected")
            break
    except Exception:
        pass


@bot.event
async def on_guild_update(before, after):
    cfg = get_guild_config(after.id)

    if not cfg.get("anti_server_rename"):
        return

    if before.name == after.name:
        return

    try:
        async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
            user = entry.user

            if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                return

            await send_anti_nuke_log(
                after,
                "Anti Server Rename",
                user,
                f"Renamed server: `{before.name}` → `{after.name}`"
            )

            try:
                await after.edit(name=before.name, reason="Anti server rename")
            except Exception:
                pass

            await punish_user(after, user.id, "Anti: server rename detected")
            break
    except Exception:
        pass


@bot.event
async def on_guild_channel_update(before, after):
    cfg = get_guild_config(after.guild.id)

    if not cfg.get("anti_channel_rename"):
        return

    if before.name == after.name:
        return

    try:
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_update):
            user = entry.user

            if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                return

            await send_anti_nuke_log(
                after.guild,
                "Anti Channel Rename",
                user,
                f"Renamed channel: {after.mention} (`{before.name}` → `{after.name}`)"
            )

            try:
                await after.edit(name=before.name, reason="Anti rename")
            except Exception:
                pass

            await punish_user(after.guild, user.id, "Anti: channel rename detected")
            break
    except Exception:
        pass

@bot.event
async def on_guild_role_create(role):
    cfg = get_guild_config(role.guild.id)

    if not cfg.get("anti_role_create"):
        return

    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            user = entry.user

            if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                return

            await send_anti_nuke_log(
                role.guild,
                "Anti Role Create",
                user,
                f"Created role: {role.mention} (`{role.name}`)"
            )

            try:
                await role.delete(reason="Anti role create")
            except Exception:
                pass

            await punish_user(role.guild, user.id, "Anti: role create detected")
            break
    except Exception:
        pass


@bot.event
async def on_webhooks_update(channel):
    cfg = get_guild_config(channel.guild.id)

    if not cfg.get("anti_webhook_create"):
        return

    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
            user = entry.user

            if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                return

            await send_anti_nuke_log(
                channel.guild,
                "Anti Webhook Create",
                user,
                f"Created webhook in: `{channel.name}`"
            )

            await punish_user(channel.guild, user.id, "Anti: webhook create detected")
            break
    except Exception:
        pass

    try:
        webhooks = await channel.webhooks()
        for webhook in webhooks:
            try:
                await webhook.delete(reason="Anti webhook")
            except Exception:
                pass
    except Exception:
        pass


@bot.event
async def on_guild_role_delete(role):
    cfg = get_guild_config(role.guild.id)

    if not cfg.get("anti_role_delete"):
        return

    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            user = entry.user

            if isinstance(user, discord.Member) and is_automod_whitelisted(user, cfg):
                return

            await send_anti_nuke_log(
                role.guild,
                "Anti Role Delete",
                user,
                f"Deleted role: `{role.name}`"
            )

            await restore_deleted_role(role.guild, role)
            await punish_user(role.guild, user.id, "Anti: role delete detected")
            break
    except Exception:
        pass


@bot.event
async def on_member_update(before, after):
    cfg = get_guild_config(after.guild.id)

    if not cfg.get("anti_role_escalation"):
        return

    added_roles = [r for r in after.roles if r not in before.roles]
    if not added_roles:
        return

    dangerous_roles = []
    for role in added_roles:
        perms = role.permissions
        if (
            perms.administrator
            or perms.manage_guild
            or perms.manage_roles
            or perms.manage_channels
        ):
            dangerous_roles.append(role)

    if not dangerous_roles:
        return

    try:
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
            user = entry.user

            if not isinstance(user, discord.Member):
                break

            if is_automod_whitelisted(user, cfg):
                return

            role_names = ", ".join(f"{r.mention} (`{r.name}`)" for r in dangerous_roles)

            await send_anti_nuke_log(
                after.guild,
                "Anti add administrator role(s)",
                user,
                f"Giving high or adm role(s) {role_names} to {after.mention} (`{after}`)"
            )

            try:
                await after.remove_roles(*dangerous_roles, reason=" giving administrator role ")
            except Exception:
                pass

            await punish_user(after.guild, user.id, "Anti: giving administrator role")
            break
    except Exception:
        pass


@bot.event
async def on_member_ban(guild, user):
    cfg = get_guild_config(guild.id)

    if not cfg.get("anti_mass_ban"):
        return

    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            mod = entry.user

            if isinstance(mod, discord.Member) and is_automod_whitelisted(mod, cfg):
                return

            await send_anti_nuke_log(
                guild,
                "Anti Mass Ban",
                mod,
                f"Banned user: `{user}`"
            )

            now = time.time()
            key = ("mass_ban", mod.id)

            nuke_tracker[key] = [t for t in nuke_tracker[key] if now - t < 3]
            nuke_tracker[key].append(now)

            if len(nuke_tracker[key]) >= 2:
                await punish_user(guild, mod.id, "Anti: mass ban detected")
            break
    except Exception:
        pass


@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        blocked = await handle_interaction_spam(interaction)
        if blocked:
            return
    except Exception:
        pass

@bot.event
async def on_member_remove(member):
    await force_status_update(member.guild)

    cfg = get_guild_config(member.guild.id)

    if cfg.get("anti_mass_kick"):
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
                mod = entry.user

                if isinstance(mod, discord.Member) and is_automod_whitelisted(mod, cfg):
                    break

                target = entry.target
                if target and getattr(target, "id", None) == member.id:
                    await send_anti_nuke_log(
                        member.guild,
                        "Anti Mass Kick",
                        mod,
                        f"Kicked user: `{member}`"
                    )

                    now = time.time()
                    key = ("mass_kick", mod.id)

                    nuke_tracker[key] = [t for t in nuke_tracker[key] if now - t < 3]
                    nuke_tracker[key].append(now)

                    if len(nuke_tracker[key]) >= 2:
                        await punish_user(member.guild, mod.id, "Anti: mass kick detected")
                    break
        except Exception:
            pass

    leave_channel_id = cfg.get("leave_channel_id")
    if leave_channel_id:
        channel = member.guild.get_channel(int(leave_channel_id))
        if channel:
            text = format_wc_text(
                cfg.get("leave_embed_text", "bye hanggang sa muling pag kikita kapatid {user} paalam"),
                member
            )
            emb = build_leave_embed(member, text)

            try:
                await fallen_safe_send(channel, embed=emb)
            except Exception:
                pass

    leave_message_channel_id = cfg.get("leave_message_channel_id")
    if leave_message_channel_id:
        msg_channel = member.guild.get_channel(int(leave_message_channel_id))
        if msg_channel:
            text = format_wc_text(
                cfg.get("leave_message_text", "paalam {user}"),
                member
            )
            emb = build_gray_message_embed(text)

            try:
                await fallen_safe_send(msg_channel, embed=emb)
            except Exception:
                pass

async def handle_ps_flow(message: discord.Message):
    if not isinstance(message.channel, discord.TextChannel):
        return

    guild_cfg = get_guild_config(message.guild.id)
    partnership_channel_id = guild_cfg.get("partnership_channel_id")
    ps_manager_role_id = guild_cfg.get("ps_manager_role_id")

    uid = message.author.id
    channel = message.channel
    key = (channel.id, uid)
    content_lower = message.content.lower()
    is_ticket = "ticket-" in channel.name.lower()

    if content_lower == "ps":
        if not is_ticket:
            return

        if on_cd(uid, 3):
            return

        cfg_ticket = get_guild_config(channel.guild.id)
        server_ad_ticket = cfg_ticket.get("server_ad")

        if not server_ad_ticket:
            return

        active_states[key] = {"step": "waiting_link", "ts": time.time()}
        await channel.send(server_ad_ticket)
        await asyncio.sleep(2)
        await channel.send("> -# Hello! please post our ad on your server, then drop your server ad or link here so I can post it too!")
        return

    if not is_ticket and key not in active_states:
        return

    st = active_states.get(key)
    if st and (time.time() - st.get("ts", time.time())) > 900:
        active_states.pop(key, None)
        return

    if key in active_states:
        state = active_states[key]
        step = state.get("step")

        if step == "waiting_posted" and "posted" in content_lower:
            server_name = "Unknown Server"
            code = state.get("invite_code")

            if code:
                try:
                    inv = await bot.fetch_invite(code)
                    if inv.guild:
                        server_name = inv.guild.name
                except Exception:
                    pass

            new_view = ClaimRoleView()
            emb = discord.Embed(
                description=f" > Get your role {message.author.mention}",
                color=EMBED_COLOR
            )
            sent = await channel.send(embed=emb, view=new_view)

            claim_messages[str(sent.id)] = {
                "partner_id": uid,
                "server_name": server_name,
                "created_at": time.time()
            }
            await save_json(CLAIMS_FILE, claim_messages)
            active_states.pop(key, None)
            return

        if step == "confirming":
            if content_lower in ["yes", "oo", "opo", "y"]:
                ps_chan = bot.get_channel(int(partnership_channel_id)) if partnership_channel_id else None
                code = state.get("invite_code")
                raw_post = state.get("raw_post")

                if ps_chan:
                    await ps_chan.send(raw_post if raw_post else f"https://discord.gg/{code}")
                    await asyncio.sleep(1)
                    await ps_chan.send(f"> rep : {message.author.mention}")

                await channel.send(
                    f">>> ## Your ad has been posted in ** <#{partnership_channel_id}> **\n"
                    f"Please let me know once our ad has been posted on your server as well.\n\n"
                    f"{message.author.mention}, please wait for __** <@&{ps_manager_role_id}> **__ to join your server.\n\n"
                    f"Once our ad has been posted on your server, type __**𝗽𝗼𝘀𝘁𝗲𝗱**__ to request your role ^^"
                )

                active_states[key]["step"] = "waiting_posted"
                active_states[key]["ts"] = time.time()
                return

            if content_lower in ["no", "hindi", "n"]:
                active_states.pop(key, None)
                await channel.send(" -# cancelled.")
                return

    m = INV_RE.search(message.content)
    if m:
        code = m.group(1)

        if BLOCK_INVITE_CODE and code.lower().strip() == BLOCK_INVITE_CODE.lower().strip():
            return

        active_states[key] = {
            "step": "confirming",
            "invite_code": code,
            "raw_post": message.content,
            "ts": time.time()
        }

        await channel.send(f"{message.content}")
        await asyncio.sleep(1)
        await channel.send(">>> Is this your server/ad link?\n\ntype **'[yes or opo]'**")
        return

    if key in active_states:
        state = active_states[key]
        step = state.get("step")

        if step == "confirming":
            if content_lower in ["yes", "oo", "opo", "y"]:
                ps_chan = bot.get_channel(int(partnership_channel_id)) if partnership_channel_id else None
                code = state.get("invite_code")
                raw_post = state.get("raw_post")

                if ps_chan:
                    await ps_chan.send(raw_post if raw_post else f"https://discord.gg/{code}")
                    await asyncio.sleep(1)
                    await ps_chan.send(f"> rep : {message.author.mention}")

                await channel.send(
                    f">>> ## Your ad has been posted in ** <#{partnership_channel_id}> **\n"
                    f"Please let me know once our ad has been posted on your server as well.\n\n"
                    f"{message.author.mention}, please wait for __** <@&{ps_manager_role_id}> **__ to join your server to serve as your rep. Thank you! ^^\n\n"
                    f"Once our ad has been posted on your server, type __**𝗽𝗼𝘀𝘁𝗲𝗱**__ to request your role ^^"
                )

                active_states[key]["step"] = "waiting_posted"
                active_states[key]["ts"] = time.time()
                return

            if content_lower in ["no", "hindi", "n"]:
                active_states.pop(key, None)
                await channel.send(" -# cancelled.")
                return

        elif step == "waiting_posted":
            if "posted" in content_lower:
                server_name = "Unknown Server"
                code = state.get("invite_code")

                if code:
                    try:
                        inv = await bot.fetch_invite(code)
                        if inv.guild:
                            server_name = inv.guild.name
                    except Exception:
                        pass

                new_view = ClaimRoleView()
                emb = discord.Embed(
                    description=f" > Get your role {message.author.mention}",
                    color=EMBED_COLOR
                )
                sent = await channel.send(embed=emb, view=new_view)

                claim_messages[str(sent.id)] = {
                    "partner_id": uid,
                    "server_name": server_name,
                    "created_at": time.time()
                }
                await save_json(CLAIMS_FILE, claim_messages)
                active_states.pop(key, None)
                return


async def handle_partnership_channel(message: discord.Message):
    guild_cfg = get_guild_config(message.guild.id)
    partnership_channel_id = guild_cfg.get("partnership_channel_id")
    ps_manager_role_id = guild_cfg.get("ps_manager_role_id")
    partner_role_id = guild_cfg.get("partner_role_id")

    if not partnership_channel_id or message.channel.id != int(partnership_channel_id):
        return

    if not isinstance(message.author, discord.Member):
        return

    has_role = bool(ps_manager_role_id) and any(r.id == int(ps_manager_role_id) for r in message.author.roles)
    if not has_role:
        return

    if INV_RE.search(message.content):
        gid = str(message.guild.id)
        m_uid = str(message.author.id)

        user_points.setdefault(gid, {})
        user_points[gid][m_uid] = user_points[gid].get(m_uid, 0) + 1
        await save_json(POINTS_FILE, user_points)

        rank = sorted(user_points[gid].items(), key=lambda x: x[1], reverse=True)
        position = next((i + 1 for i, v in enumerate(rank) if v[0] == m_uid), 1)

        emb = discord.Embed(
            description=(
                f"Thank you {message.author.mention} for new affiliate! \n\n"
                f"Partner point: `#{position}` - `{user_points[gid][m_uid]}`\n"
                f"Weekly point: `#{position}` - `{user_points[gid][m_uid]}` "
            ),
            color=EMBED_COLOR
        )

        emb.set_thumbnail(url=message.author.display_avatar.url)

        guild = message.guild
        server_name = guild.name if guild else "Unknown Server"
        server_icon = guild.icon.url if (guild and guild.icon) else message.author.display_avatar.url
        emb.set_footer(text=f"{server_name}", icon_url=server_icon)

        await message.channel.send(embed=emb)

        try:
            await message.add_reaction("❤️")
        except Exception:
            pass

    if message.mentions:
        target_user = message.mentions[0]
        partner_role = message.guild.get_role(int(partner_role_id)) if partner_role_id else None

        server_name = "Unknown Server"
        async for msg in message.channel.history(limit=60):
            mm = INV_RE.search(msg.content)
            if not mm:
                continue

            code = mm.group(1)
            if BLOCK_INVITE_CODE and code.lower().strip() == BLOCK_INVITE_CODE.lower().strip():
                continue

            try:
                inv = await bot.fetch_invite(code)
                if inv.guild:
                    server_name = inv.guild.name
                    break
            except Exception:
                continue

        if partner_role:
            try:
                await target_user.add_roles(partner_role, reason="PS Manager approved partner")
                await message.channel.send(f"thankyou! {target_user.mention} {partner_role.mention} ")
            except Exception:
                pass

        try:
            await log_partnership(target_user, server_name, partner_role, message.author)
        except Exception:
            pass

        try:
            await message.add_reaction("🩷")
        except Exception:
            pass

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    guild_cfg = get_guild_config(message.guild.id) if message.guild else {}

    ps_prefix = str(guild_cfg.get("ps_prefix", "ps ")).strip().lower()
    util_prefix = str(guild_cfg.get("util_prefix", ",")).strip().lower()

    low = message.content.lower().strip()

    if message.guild:
        gid = str(message.guild.id)
        uid = str(message.author.id)

        if gid in afk_users and uid in afk_users[gid]:
            data = afk_users[gid].pop(uid)

            since = int(data.get("since", time.time()))
            elapsed = int(time.time() - since)

            if elapsed < 60:
                afk_for = f"{elapsed}s"
            elif elapsed < 3600:
                afk_for = f"{elapsed // 60}m"
            elif elapsed < 86400:
                afk_for = f"{elapsed // 3600}h"
            else:
                afk_for = f"{elapsed // 86400}d"

            try:
                await fallen_safe_send(
                    message.channel,
                    embed=discord.Embed(
                        description=f"`✅` welcome back {message.author.mention}, you were afk for `{afk_for}`",
                        color=EMBED_COLOR
                    )
                )
            except Exception:
                pass

    if message.guild and message.mentions:
        gid = str(message.guild.id)

        for user in message.mentions:
            afk_data = afk_users.get(gid, {}).get(str(user.id))
            if afk_data:
                since = int(afk_data.get("since", time.time()))
                elapsed = int(time.time() - since)

                if elapsed < 60:
                    afk_for = f"{elapsed}s"
                elif elapsed < 3600:
                    afk_for = f"{elapsed // 60}m"
                elif elapsed < 86400:
                    afk_for = f"{elapsed // 3600}h"
                else:
                    afk_for = f"{elapsed // 86400}d"

                now = time.time()
                afk_key = (message.channel.id, user.id)
                last_ping = afk_notify_cache.get(afk_key, 0)

                if now - last_ping >= 10:
                    afk_notify_cache[afk_key] = now

                    emb = discord.Embed(
                        description=f"`💤` {user.mention} is afk: `{afk_data['reason']}` — `{afk_for} ago`",
                        color=EMBED_COLOR
                    )

                    try:
                        await fallen_safe_send(message.channel, embed=emb)
                    except Exception:
                        pass

                break

    if low in [f"{util_prefix}help", f"{util_prefix} help"]:
        await send_4t_help(message.channel, message.guild, message.author)
        return

    if low.startswith(f"{util_prefix}prefix ") or low.startswith(f"{util_prefix} prefix "):
        if message.guild and message.author.guild_permissions.administrator:
            parts = message.content.split(maxsplit=2)
            if len(parts) >= 3:
                new_prefix = parts[2].strip()
                if new_prefix:
                    guild_cfg["util_prefix"] = new_prefix.strip()
                    save_config()
                    try:
                        await fallen_safe_send(
                            message.channel,
                            content=f"> 02 prefix set to `{new_prefix}`"
                        )
                    except Exception:
                        pass
        return

    if low.startswith(f"{ps_prefix}prefix ") or low.startswith(f"{ps_prefix} prefix "):
        if message.guild and message.author.guild_permissions.administrator:
            parts = message.content.split(maxsplit=2)
            if len(parts) >= 3:
                new_prefix = parts[2].strip()
                if new_prefix:
                    guild_cfg["ps_prefix"] = new_prefix + " "
                    save_config()
                    try:
                        await fallen_safe_send(
                            message.channel,
                            content=f"> 01 prefix set to `{new_prefix}`"
                        )
                    except Exception:
                        pass
        return

    if bot.user and message.content in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
        emb = discord.Embed(
            description=(
                f"> 01 prefix: `{guild_cfg.get('ps_prefix', 'ps ').strip()}`\n"
                f"> 02 prefix: `{guild_cfg.get('util_prefix', ',')}`"
            ),
            color=EMBED_COLOR
        )
        try:
            await fallen_safe_send(
                message.channel,
                embed=emb,
                reference=message.to_reference(fail_if_not_exists=False)
            )
        except Exception:
            pass
        return

    # AUTOMOD
    if message.guild and isinstance(message.author, discord.Member):
        automod_enabled = guild_cfg.get("automod_enabled", False)

        if automod_enabled and not is_automod_whitelisted(message.author, guild_cfg):

            if guild_cfg.get("antilink_enabled", False):

                if not message.channel.name.startswith("ticket-") and URL_RE.search(message.content):
                    try:
                        await message.delete()
                    except Exception:
                        pass

                    try:
                        await message.author.timeout(
                            discord.utils.utcnow() + timedelta(minutes=5),
                            reason="AutoMod: link detected"
                        )
                    except Exception:
                        try:
                            await fallen_safe_send(
                                message.channel,
                                embed=discord.Embed(
                                    description="`❌` can't timeout that user. check my permissions and role position",
                                    color=EMBED_COLOR
                                ),
                                delete_after=5
                            )
                        except Exception:
                            pass
                        return

                    await send_automod_log(
                        message.guild,
                        guild_cfg,
                        "AutoMod Timeout",
                        message.author,
                        "Link detected - 5 minutes timeout",
                        message.content
                    )

                    try:
                        await fallen_safe_send(
                            message.channel,
                            embed=discord.Embed(
                                description=f"`❌` {message.author.mention} timed out for 5 minutes (link detected)",
                                color=EMBED_COLOR
                            ),
                            delete_after=5
                        )
                    except Exception:
                        pass
                    return

            # ANTISPAM = 5 MSGS 
            if guild_cfg.get("antispam_enabled", False):
                now = time.time()
                key = (message.guild.id, message.author.id)
                spam_cache[key] = [t for t in spam_cache[key] if now - t < 6]
                spam_cache[key].append(now)

                if len(spam_cache[key]) >= 5:
                    try:
                        await message.delete()
                    except Exception:
                        pass

                    try:
                        await message.author.timeout(
                            discord.utils.utcnow() + timedelta(minutes=10),
                            reason="AutoMod: spam detected"
                        )
                    except Exception:
                        try:
                            await fallen_safe_send(
                                message.channel,
                                embed=discord.Embed(
                                    description="❌ can't timeout that user. check my permissions and role position",
                                    color=EMBED_COLOR
                                ),
                                delete_after=5
                            )
                        except Exception:
                            pass
                        return

                    await send_automod_log(
                        message.guild,
                        guild_cfg,
                        "AutoMod Timeout",
                        message.author,
                        "Spam detected - 10 minutes timeout",
                        message.content
                    )

                    try:
                        await fallen_safe_send(
                            message.channel,
                            embed=discord.Embed(
                                description=f"`❌` {message.author.mention} timed out for 10 minutes (spam detected)",
                                color=EMBED_COLOR
                            ),
                            delete_after=5
                        )
                    except Exception:
                        pass

                    spam_cache[key].clear()
                    return

    # AUTORESPONDER
    if message.guild and guild_cfg.get("autoresponder_enabled", False):
        responses = guild_cfg.get("autoresponses", {})
        reply = responses.get(low)

        if reply:
            try:
                await fallen_safe_send(message.channel, content=reply)
            except Exception:
                pass

# AUTOREACT
    if message.guild and not message.author.bot:
        autoreact_users = guild_cfg.get("autoreact_users", {})
        emoji_key = autoreact_users.get(str(message.author.id))

        if emoji_key:
            now = time.time()
            ar_key = (message.guild.id, message.author.id)
            last = autoreact_cooldowns.get(ar_key, 0)

            if now - last >= 1.2:
                autoreact_cooldowns[ar_key] = now
                reaction_obj = get_reaction_object(bot, emoji_key)

                try:
                    await message.add_reaction(reaction_obj)
                except Exception:
                    pass

    await handle_ps_flow(message)
    await handle_partnership_channel(message)

    # STICKY MESSAGE 
    if message.guild and not message.author.bot:
        cid = message.channel.id

        if cid in sticky_messages:
            now = time.time()
            last_sticky = sticky_cooldown.get(cid, 0)

            if now - last_sticky >= 8:
                sticky_cooldown[cid] = now
                data = sticky_messages[cid]

                if message.id != data.get("msg_id"):
                    try:
                        old = await message.channel.fetch_message(data["msg_id"])
                        await old.delete()
                    except Exception:
                        pass

                    try:
                        new_msg = await message.channel.send(data["content"])
                        sticky_messages[cid]["msg_id"] = new_msg.id
                    except Exception:
                        pass

    await bot.process_commands(message)

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def ps_setup(
    ctx,
    partnership_channel: discord.TextChannel = None,
    ps_manager_role: discord.Role = None,
    partner_role: discord.Role = None
):
    if not partnership_channel or not ps_manager_role or not partner_role:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('ps_prefix', 'ps').strip()} setup #pschannel @psmanager @partner`",
                color=0x2b2d31
            )
        )

    guild_cfg = get_guild_config(ctx.guild.id)
    guild_cfg["partnership_channel_id"] = partnership_channel.id
    guild_cfg["ps_manager_role_id"] = ps_manager_role.id
    guild_cfg["partner_role_id"] = partner_role.id
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=(
                f"`✅` ps channel : {partnership_channel.mention}\n"
                f"`✅` ps manager : {ps_manager_role.mention}\n"
                f"`✅` role partner : {partner_role.mention}"
            ),
            color=0x2b2d31
        )
    )


@bot.group(name="anti", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def cmd_anti(ctx, mode=None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if mode in ["on", "off"]:
        cfg = get_guild_config(ctx.guild.id)
        state = (mode == "on")

        cfg["automod_enabled"] = state
        cfg["antilink_enabled"] = state
        cfg["antispam_enabled"] = state
        cfg["anti_channel_create"] = state
        cfg["anti_role_create"] = state
        cfg["anti_role_delete"] = state
        cfg["anti_webhook_create"] = state
        cfg["anti_bot_add"] = state
        cfg["anti_channel_delete"] = state
        cfg["anti_server_rename"] = state
        cfg["anti_channel_rename"] = state
        cfg["anti_role_escalation"] = state
        cfg["anti_mass_ban"] = state
        cfg["anti_mass_kick"] = state

        save_config()

        emoji = "✅" if mode == "on" else "❌"

        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`{emoji}` anti nuke {mode}",
                color=0x2b2d31
            )
        )

    await fallen_safe_send(
        ctx.channel,
        content=(
            f"use:\n"
            f"`{prefix}anti channel on/off`\n"
            f"`{prefix}anti channeldelete on/off`\n"
            f"`{prefix}anti crename on/off`\n"
            f"`{prefix}anti role on/off`\n"
            f"`{prefix}anti webhook on/off`\n"
            f"`{prefix}anti botadd on/off`\n"
            f"`{prefix}anti admin on/off`\n"
            f"`{prefix}anti massban on/off`\n"
            f"`{prefix}anti masskick on/off`\n"
            f"`{prefix}set punishment ban/kick`\n"
            f"`{prefix}anti on/off`\n"
            f"`{prefix}anti status` or `{prefix}as`"
        )
    )


@bot.command(name="as")
@commands.has_permissions(administrator=True)
async def cmd_anti_status_alias(ctx):
    await cmd_anti_status(ctx)

@cmd_anti.command(name="status")
@commands.has_permissions(administrator=True)
async def cmd_anti_status(ctx):
    cfg = get_guild_config(ctx.guild.id)

    def format_toggle(value):
        return "✅" if value else "❌"

    try:
        owner = ctx.guild.owner or await bot.fetch_user(ctx.guild.owner_id)
        owner_icon = owner.display_avatar.url
    except Exception:
        owner_icon = ctx.author.display_avatar.url

    desc = ">>> \n"
    desc += f"`{format_toggle(cfg.get('automod_enabled', False))}` automod\n"
    desc += f"`{format_toggle(cfg.get('antilink_enabled', False))}` anti link\n"
    desc += f"`{format_toggle(cfg.get('antispam_enabled', False))}` anti spam\n"
    desc += f"`{format_toggle(cfg.get('anti_channel_create', False))}` anti channel create\n"
    desc += f"`{format_toggle(cfg.get('anti_role_create', False) or cfg.get('anti_role_delete', False))}` anti role create/delete\n"
    desc += f"`{format_toggle(cfg.get('anti_webhook_create', False))}` anti webhook create\n"
    desc += f"`{format_toggle(cfg.get('anti_bot_add', False))}` anti bot add\n"
    desc += f"`{format_toggle(cfg.get('anti_channel_delete', False))}` anti channel delete\n"
    desc += f"`{format_toggle(cfg.get('anti_server_rename', False))}` anti server rename\n"
    desc += f"`{format_toggle(cfg.get('anti_channel_rename', False))}` anti channel rename\n"
    desc += f"`{format_toggle(cfg.get('anti_role_escalation', False))}` anti admin role\n"
    desc += f"`{format_toggle(cfg.get('anti_mass_ban', False))}` anti mass ban\n"
    desc += f"`{format_toggle(cfg.get('anti_mass_kick', False))}` anti mass kick\n"
    desc += f"`{'✅' if cfg.get('anti_interaction_spam', False) else '❌'}` anti interaction spam\n\n"

    desc += f"`💀` punishment : **`{cfg.get('anti_punish', 'ban')}`**"

    emb = discord.Embed(
        description=desc,
        color=0x2b2d31
    )

    emb.set_author(
        name="♰ Anti Nuke Status",
        icon_url=owner_icon
    )

    now = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"{ctx.guild.name} | Today at : {now}",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@cmd_anti.command(name="channel", aliases=["cc"])
@commands.has_permissions(administrator=True)
async def anti_channel(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti channel on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_channel_create"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti channel create {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="role", aliases=["cr"])
@commands.has_permissions(administrator=True)
async def anti_role(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti role on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_role_create"] = (mode == "on")
    cfg["anti_role_delete"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti role {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="webhook", aliases=["cw"])
@commands.has_permissions(administrator=True)
async def anti_webhook(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti webhook on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_webhook_create"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti webhook {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="botadd", aliases=["ab"])
@commands.has_permissions(administrator=True)
async def anti_botadd(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti botadd on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_bot_add"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti bot add {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="channeldelete", aliases=["cd"])
@commands.has_permissions(administrator=True)
async def anti_channel_delete(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti channeldelete on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_channel_delete"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti channel delete {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="admin", aliases=["ar"])
@commands.has_permissions(administrator=True)
async def anti_admin(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti admin on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_role_escalation"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti admin role {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="srename")
@commands.has_permissions(administrator=True)
async def anti_server_rename(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti srename on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_server_rename"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti server rename {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="crename")
@commands.has_permissions(administrator=True)
async def anti_channel_rename(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti crename on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_channel_rename"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti channel rename {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="massban", aliases=["mb"])
@commands.has_permissions(administrator=True)
async def anti_massban(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti massban on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_mass_ban"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti mass ban {mode}",
            color=0x2b2d31
        )
    )


@cmd_anti.command(name="masskick", aliases=["mk"])
@commands.has_permissions(administrator=True)
async def anti_masskick(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            content=f"use: `{prefix}anti masskick on/off`"
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_mass_kick"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti mass kick {mode}",
            color=0x2b2d31
        )
    )


@bot.command(name="set", aliases=["s", "sp", "setpunish"])
@commands.has_permissions(administrator=True)
async def set_punishment(ctx, category=None, action=None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if category != "punishment" or not action:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}set punishment ban/kick` or `{prefix}s punishment b/k`",
                color=0x2b2d31
            )
        )

    action = action.lower()

    if action == "b":
        action = "ban"
    elif action == "k":
        action = "kick"

    if action not in ["ban", "kick"]:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}set punishment ban/kick` or `{prefix}s punishment b/k`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_punish"] = action
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`💀` punishment set to `{action}`",
            color=0x2b2d31
        )
    )

@bot.command(name="setad")
@commands.has_permissions(administrator=True)
async def cmd_setad(ctx, *, ad=None):
    if not ad:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}setad (your server ad or link)`",
                color=EMBED_COLOR
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["server_ad"] = ad
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`✅` server ad set!\n\n{ad}",
            color=EMBED_COLOR
        )
    )

@bot.command(name="stat")
@commands.has_permissions(administrator=True)
async def ps_stat(ctx):

    guild_cfg = get_guild_config(ctx.guild.id)

    emb = discord.Embed(title="PS STAT", color=EMBED_COLOR)

    emb.add_field(
        name="partnership channel",
        value=f"<#{guild_cfg['partnership_channel_id']}>" if guild_cfg.get("partnership_channel_id") else "not set",
        inline=False
    )

    emb.add_field(
        name="ps manager role",
        value=f"<@&{guild_cfg['ps_manager_role_id']}>" if guild_cfg.get("ps_manager_role_id") else "not set",
        inline=False
    )

    emb.add_field(
        name="partner role",
        value=f"<@&{guild_cfg['partner_role_id']}>" if guild_cfg.get("partner_role_id") else "not set",
        inline=False
    )

    emb.add_field(
        name="ps prefix",
        value=f"`{guild_cfg.get('ps_prefix', 'ps ').strip()}`",
        inline=False
    )

    emb.add_field(
        name="prefix",
        value=f"`{guild_cfg.get('util_prefix', ',')}`",
        inline=False
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="list")
async def ps_list(ctx):

    pts_map = load_points_fresh()
    gid = str(ctx.guild.id)

    if gid not in pts_map or not pts_map[gid]:
        return await fallen_safe_send(ctx.channel, content="No records found")

    sorted_pts = sorted(pts_map[gid].items(), key=lambda x: x[1], reverse=True)[:15]

    emb = discord.Embed(title="PS LEADERBOARD", color=EMBED_COLOR)

    lines = []
    for i, (uid_key, pts) in enumerate(sorted_pts, 1):
        member = ctx.guild.get_member(int(uid_key)) if ctx.guild else None
        user_display = member.mention if member else "User Left"
        lines.append(f"**{i}.** {user_display} `{uid_key}` : **{pts} pts**")

    emb.description = "\n".join(lines)

    if ctx.guild and ctx.guild.icon:
        emb.set_thumbnail(url=ctx.guild.icon.url)

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def ps_remove(ctx, member: discord.Member = None):
    if not member:
        await fallen_safe_send(
            ctx.channel,
            content="> -# please mention the user to remove from leaderboard."
        )
        return

    gid = str(ctx.guild.id)
    m_id = str(member.id)

    if gid not in user_points:
        user_points[gid] = {}

    if m_id in user_points[gid]:
        del user_points[gid][m_id]
        await save_json(POINTS_FILE, user_points)
        await fallen_safe_send(
            ctx.channel,
            content=f"> Successfully removed {member.mention} from the leaderboard."
        )
    else:
        await fallen_safe_send(
            ctx.channel,
            content=f"> -# {member.mention} is not in the leaderboard records."
        )

@bot.command(name="av")
async def cmd_avatar(ctx, member: discord.Member=None):

    member = member or ctx.author

    emb = discord.Embed(
        title=f"{member.name}'s avatar",
        color=EMBED_COLOR
    )

    emb.set_image(url=member.display_avatar.url)

    await fallen_safe_send(ctx.channel, embed=emb)

@bot.command(name="bn")
async def cmd_banner(ctx, member: discord.Member=None):

    member = member or ctx.author
    user = await bot.fetch_user(member.id)

    if user.banner:

        emb = discord.Embed(
            title=f"{member.name}'s banner",
            color=EMBED_COLOR
        )

        emb.set_image(url=user.banner.url)

        await fallen_safe_send(ctx.channel, embed=emb)

    else:
        await fallen_safe_send(ctx.channel, content="user has no banner.")


@bot.command(name="userinfo", aliases=["ui"])
async def cmd_userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author

    emb = discord.Embed(
        description=f"**{member}**",
        color=EMBED_COLOR
    )
    emb.set_thumbnail(url=member.display_avatar.url)

    emb.add_field(
        name="User",
        value=f"{member.mention}\n`{member.id}`",
        inline=True
    )
    emb.add_field(
        name="Joined Server",
        value=f"`{member.joined_at.strftime('%m/%d/%Y | %I:%M %p')}`" if member.joined_at else "`unknown`",
        inline=True
    )
    emb.add_field(
        name="Account Created",
        value=f"`{member.created_at.strftime('%m/%d/%Y | %I:%M %p')}`",
        inline=True
    )

    roles = [r for r in reversed(member.roles) if r.name != "@everyone"]
    role_text = " ".join(r.mention for r in roles[:10])
    if len(roles) > 10:
        role_text += f" `+{len(roles)-10} more`"

    emb.add_field(
        name="Roles",
        value=role_text if role_text else "`none`",
        inline=False
    )

    top_role = member.top_role if member.top_role.name != "@everyone" else None
    emb.add_field(
        name="Highest Role",
        value=top_role.mention if top_role else "`none`",
        inline=True
    )

    perms = []
    if top_role:
        for perm, value in top_role.permissions:
            if value:
                perms.append(perm.replace("_", " ").title())

    perm_text = ", ".join(perms[:10])
    if len(perms) > 10:
        perm_text += " ..."

    emb.add_field(
        name="Permissions",
        value=perm_text if perm_text else "`none`",
        inline=False
    )

    now = ph_now().strftime("%m/%d/%Y | %I:%M %p")
    emb.set_footer(
        text=f"Requested by {ctx.author} | Today at : {now}",
        icon_url=ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="serverinfo", aliases=["si"])
async def cmd_serverinfo(ctx):
    g = ctx.guild

    owner = g.owner
    owner_name = owner.name if owner else "unknown"
    owner_mention = owner.mention if owner else "unknown"
    owner_id = f"`{owner.id}`" if owner else "`unknown`"

    boost_count = g.premium_subscription_count
    boost_level = g.premium_tier

    role_count = len(g.roles)
    total_channels = len(g.channels)

    created_abs = g.created_at.strftime("%B %d, %Y %I:%M %p")
    created_rel = discord.utils.format_dt(g.created_at, style="R")

    emoji_count = len(g.emojis)

    if g.emojis:
        emoji_preview = ""
        shown = 0

        for e in g.emojis:
            piece = f"{str(e)} "
            if len(emoji_preview) + len(piece) > 900:
                break
            emoji_preview += piece
            shown += 1

        emoji_preview = emoji_preview.strip()

        remaining = emoji_count - shown
        if remaining > 0:
            extra_text = f" `+{remaining} more`"
            if len(emoji_preview) + len(extra_text) <= 1024:
                emoji_preview += extra_text
    else:
        emoji_preview = "`none`"

    emb = discord.Embed(
        title=g.name,
        color=0x2b2d31
    )

    emb.add_field(
        name="Server Owner",
        value=f"{owner_mention} ({owner_name})",
        inline=False
    )

    emb.add_field(
        name="ID",
        value=owner_id,
        inline=False
    )

    emb.add_field(
        name="Members",
        value=f"`{g.member_count}`",
        inline=False
    )

    emb.add_field(
        name="Server Boost Status",
        value=f"`{boost_count} Boosts (Level {boost_level})`",
        inline=False
    )

    emb.add_field(
        name="Roles",
        value=f"`{role_count}`",
        inline=False
    )

    emb.add_field(
        name="Channels",
        value=f"`{total_channels}`",
        inline=False
    )

    emb.add_field(
        name="Created",
        value=f"`{created_abs}` ({created_rel})",
        inline=False
    )

    emb.add_field(
        name=f"Emoji List [{emoji_count}]",
        value=emoji_preview,
        inline=False
    )

    if g.icon:
        emb.set_thumbnail(url=g.icon.url)

    try:
        full_guild = await bot.fetch_guild(g.id)
        if full_guild.banner:
            emb.set_image(url=full_guild.banner.url)
    except Exception:
        pass

    now_text = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"Requested by {ctx.author} | Today at: {now_text} | ID: {g.id}",
        icon_url=ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="roleinfo", aliases=["ri"])
async def cmd_roleinfo(ctx, role: discord.Role):
    emb = discord.Embed(
        description=f"**{role.name}**",
        color=role.color if role.color.value else EMBED_COLOR
    )

    if bot.user:
        emb.set_thumbnail(url=bot.user.display_avatar.url)

    emb.add_field(
        name="Role",
        value=f"{role.mention}\n`{role.id}`",
        inline=True
    )
    emb.add_field(
        name="Members",
        value=f"`{len(role.members)}`",
        inline=True
    )
    emb.add_field(
        name="Created",
        value=f"`{role.created_at.strftime('%m/%d/%Y | %I:%M %p')}`",
        inline=True
    )

    perms = []
    for perm, value in role.permissions:
        if value:
            perms.append(perm.replace("_", " ").title())

    perm_text = ", ".join(perms[:15])
    if len(perms) > 15:
        perm_text += " ..."

    emb.add_field(
        name="Permissions",
        value=perm_text if perm_text else "`none`",
        inline=False
    )

    now = ph_now().strftime("%m/%d/%Y | %I:%M %p")
    emb.set_footer(
        text=f"Requested by {ctx.author} | Today at : {now}",
        icon_url=ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="botinfo", aliases=["bi"])
async def cmd_botinfo(ctx):
    total_users = sum(g.member_count for g in bot.guilds if g.member_count)

    uptime_seconds = int(time.time() - bot_start_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60

    uptime_parts = []
    if days > 0:
        uptime_parts.append(f"{days}d")
    if hours > 0:
        uptime_parts.append(f"{hours}h")
    if minutes > 0 or not uptime_parts:
        uptime_parts.append(f"{minutes}m")

    uptime_text = " ".join(uptime_parts)

    guild_cfg = get_guild_config(ctx.guild.id)
    util_prefix = guild_cfg.get("util_prefix", ",")

    emb = discord.Embed(
        description=f"**{bot.user}**",
        color=EMBED_COLOR
    )

    emb.set_thumbnail(url=bot.user.display_avatar.url)

    emb.add_field(
        name="Bot",
        value=f"{bot.user}\n`{bot.user.id}`",
        inline=True
    )
    emb.add_field(
        name="Servers",
        value=f"`{len(bot.guilds)}`",
        inline=True
    )
    emb.add_field(
        name="Users",
        value=f"`{total_users}`",
        inline=True
    )
    emb.add_field(
        name="Uptime",
        value=f"`{uptime_text}`",
        inline=True
    )
    emb.add_field(
        name="Prefix",
        value=f"`{util_prefix}`",
        inline=True
    )
    emb.add_field(
        name="Developer",
        value="`fallen`",
        inline=True
    )

    now = ph_now().strftime("%m/%d/%Y | %I:%M %p")
    emb.set_footer(
        text=f"Requested by {ctx.author} | Today at : {now}",
        icon_url=ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)

@bot.command(name="role")
@commands.has_permissions(manage_roles=True)
@commands.cooldown(1, 3, commands.BucketType.user)
async def cmd_role(ctx, member: discord.Member = None, role: discord.Role = None):
    if not member or not role:
        emb = discord.Embed(
            description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}automod on/off`",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        emb = discord.Embed(
            description="`❌` can't find my bot in this server",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    if not me.guild_permissions.manage_roles:
        emb = discord.Embed(
            description="`❌` i need `Manage Roles` permission",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    if role >= me.top_role:
        emb = discord.Embed(
            description="`❌` can't add that role, it's higher than my role",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    if member.top_role >= me.top_role and member != ctx.guild.owner:
        emb = discord.Embed(
            description="`❌` can't use `@everyone` role",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    if role.is_default():
        emb = discord.Embed(
            description="`❌` can't use `@everyone` role",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    dangerous_role = (
        role.permissions.administrator
        or role.permissions.manage_guild
        or role.permissions.manage_roles
        or role.permissions.manage_channels
    )

    guild_cfg = get_guild_config(ctx.guild.id)
    is_bot_owner = (ctx.author.id == OWNER_ID)
    is_wl = is_automod_whitelisted(ctx.author, guild_cfg)

    if dangerous_role and not is_bot_owner and not is_wl:
        emb = discord.Embed(
            description="`❌` only whitelisted users/roles can give high/adm roles",
            color=EMBED_COLOR
        )
        return await fallen_safe_send(ctx.channel, embed=emb)

    try:
        if role in member.roles:
            ok = await fallen_safe_remove_role(
                member,
                role,
                reason=f"role toggle by {ctx.author}"
            )

            if ok:
                emb = discord.Embed(
                    description=f"`✅` role removed: {member.mention} {role.mention}",
                    color=EMBED_COLOR
                )
                await fallen_safe_send(ctx.channel, embed=emb)
            else:
                emb = discord.Embed(
                    description="`❌` failed to remove role. try again in a few seconds",
                    color=EMBED_COLOR
                )
                await fallen_safe_send(ctx.channel, embed=emb)

        else:
            ok = await fallen_safe_add_role(
                member,
                role,
                reason=f"role toggle by {ctx.author}"
            )

            if ok:
                emb = discord.Embed(
                    description=f"`✅` role added: {member.mention} {role.mention}",
                    color=EMBED_COLOR
                )
                await fallen_safe_send(ctx.channel, embed=emb)
            else:
                emb = discord.Embed(
                    description="`❌` failed to add role. try again in a few seconds",
                    color=EMBED_COLOR
                )
                await fallen_safe_send(ctx.channel, embed=emb)

    except discord.Forbidden:
        emb = discord.Embed(
            description="`❌` can't do that, check my role position.",
            color=EMBED_COLOR
        )
        await fallen_safe_send(ctx.channel, embed=emb)

    except Exception as e:
        emb = discord.Embed(
            description=f"`❌` error: `{e}`",
            color=EMBED_COLOR
        )
        await fallen_safe_send(ctx.channel, embed=emb)

@cmd_role.error
async def cmd_role_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        emb = discord.Embed(
            description=f"`❌` slow down. try again in `{round(error.retry_after, 1)}s`",
            color=EMBED_COLOR
        )
        await fallen_safe_send(ctx.channel, embed=emb)

@bot.group(name="autoresponder", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def cmd_autoresponder(ctx, mode=None):
    if mode in ["on", "off"]:
        cfg = get_guild_config(ctx.guild.id)
        cfg["autoresponder_enabled"] = (mode == "on")
        save_config()

        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`{'✅' if mode == 'on' else '❌'}` autoresponder {mode}",
                color=EMBED_COLOR
            )
        )

    return await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=(
                "`❌` use:\n"
                "`,autoresponder on/off`\n"
                "`,autoresponder add trigger | reply`\n"
                "`,autoresponder remove trigger`\n"
                "`,autoresponder list`"
            ),
            color=EMBED_COLOR
        )
    )


@cmd_autoresponder.command(name="add")
@commands.has_permissions(administrator=True)
async def cmd_autoresponder_add(ctx, *, data=None):
    if not data or "|" not in data:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}autoresponder add trigger | reply`",
                color=EMBED_COLOR
            )
        )

    trigger, reply = [x.strip() for x in data.split("|", 1)]

    if not trigger or not reply:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}autoresponder add trigger | reply`",
                color=EMBED_COLOR
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    responses = cfg.setdefault("autoresponses", {})

    responses[trigger.lower()] = reply
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`✅` added:\n`{trigger}` → `{reply}`",
            color=EMBED_COLOR
        )
    )

@cmd_autoresponder.command(name="remove")
@commands.has_permissions(administrator=True)
async def cmd_autoresponder_remove(ctx, *, trigger=None):
    if not trigger:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}autoresponder remove trigger`",
                color=EMBED_COLOR
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    responses = cfg.setdefault("autoresponses", {})

    if trigger.lower() not in responses:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` not found",
                color=EMBED_COLOR
            )
        )

    responses.pop(trigger.lower(), None)
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`✅` removed `{trigger}`",
            color=EMBED_COLOR
        )
    )


@cmd_autoresponder.command(name="list")
@commands.has_permissions(administrator=True)
async def cmd_autoresponder_list(ctx):
    cfg = get_guild_config(ctx.guild.id)
    responses = cfg.get("autoresponses", {})

    if not responses:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` empty list",
                color=EMBED_COLOR
            )
        )

    lines = []
    for t, r in responses.items():
        lines.append(f"`{t}` → `{r}`")

    emb = discord.Embed(
        title="Autoresponder",
        description="\n".join(lines),
        color=EMBED_COLOR
    )

    await fallen_safe_send(ctx.channel, embed=emb)

@bot.command(name="afk")
async def cmd_afk(ctx, *, reason=None):
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)

    if not reason:
        reason = "no reason provided"

    afk_users.setdefault(gid, {})
    afk_users[gid][uid] = {
        "reason": reason,
        "since": time.time()
    }

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`💤` {ctx.author.mention} is now afk: `{reason}`",
            color=0x2b2d31
        )
    )


@bot.command(name="snipe")
async def cmd_snipe(ctx, index: int = 1):
    data_list = snipe_cache.get(ctx.channel.id)

    if not data_list:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` nothing to snipe",
                color=EMBED_COLOR
            )
        )

    if index < 1 or index > len(data_list):
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` choose between 1 - {len(data_list)}",
                color=EMBED_COLOR
            )
        )

    data = data_list[index - 1]

    emb = discord.Embed(
        description=data["content"] if data.get("content") else "*no text*",
        color=EMBED_COLOR
    )

    emb.set_author(
        name=data.get("author_name", "Unknown User"),
        icon_url=data.get("avatar")
    )

    if data.get("attachments"):
        emb.set_image(url=data["attachments"][0])
    elif data.get("stickers"):
        emb.set_image(url=data["stickers"][0])

    emb.set_footer(text=f"{index}/{len(data_list)} • deleted at {data['created_at']}")

    await fallen_safe_send(ctx.channel, embed=emb)

@bot.command(name="automod")
@commands.has_permissions(administrator=True)
async def cmd_automod(ctx, mode=None):
    if mode not in ["on", "off"]:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` use: `,automod on/off`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["automod_enabled"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` automod {mode}",
            color=0x2b2d31
        )
    )


@bot.command(name="antilink")
@commands.has_permissions(administrator=True)
async def cmd_antilink(ctx, mode=None):
    if mode not in ["on", "off"]:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}antispam on/off`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["antilink_enabled"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti link {mode}",
            color=0x2b2d31
        )
    )

@bot.command(name="antiinteraction", aliases=["ais"])
@commands.has_permissions(administrator=True)
async def cmd_antiinteraction(ctx, mode=None):
    if mode not in ["on", "off"]:
        prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}antiinteraction on/off`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["anti_interaction_spam"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti interaction spam {mode}",
            color=0x2b2d31
        )
    )

@bot.command(name="antispam")
@commands.has_permissions(administrator=True)
async def cmd_antispam(ctx, mode=None):
    if mode not in ["on", "off"]:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` use: `,antispam on/off`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["antispam_enabled"] = (mode == "on")
    save_config()

    emoji = "✅" if mode == "on" else "❌"

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`{emoji}` anti spam {mode}",
            color=0x2b2d31
        )
    )


@bot.command(name="automodlogs")
@commands.has_permissions(administrator=True)
async def cmd_automodlogs(ctx, channel: discord.TextChannel = None):
    if not channel:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}automodlogs #channel`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg["automod_log_channel_id"] = channel.id
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`✅` automod logs → {channel.mention}",
            color=0x2b2d31
        )
    )


@bot.command(name="wlrole")
@commands.has_permissions(administrator=True)
async def cmd_wlrole(ctx, role: discord.Role = None):
    if not role:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{get_guild_config(ctx.guild.id).get('util_prefix', ',')}wlrole @role`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg.setdefault("automod_whitelist_role_ids", [])

    if role.id in cfg["automod_whitelist_role_ids"]:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` already whitelisted: {role.mention}",
                color=0x2b2d31
            )
        )

    cfg["automod_whitelist_role_ids"].append(role.id)
    save_config()

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`✅` added to whitelist: {role.mention}",
            color=0x2b2d31
        )
    )


@bot.group(name="wl", invoke_without_command=True)
@commands.has_permissions(administrator=True)
async def cmd_wl(ctx):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`❌` use:\n`{prefix}wl list`\n`{prefix}wl add @role`\n`{prefix}wl remove @role`",
            color=0x2b2d31
        )
    )

@cmd_wl.command(name="list")
@commands.has_permissions(administrator=True)
async def cmd_wl_list(ctx):
    cfg = get_guild_config(ctx.guild.id)

    wl_role_ids = cfg.get("automod_whitelist_role_ids", [])
    wl_user_ids = cfg.get("automod_whitelist_user_ids", [])

    roles = [ctx.guild.get_role(rid) for rid in wl_role_ids if ctx.guild.get_role(rid)]
    users = [ctx.guild.get_member(uid) for uid in wl_user_ids if ctx.guild.get_member(uid)]

    if not roles and not users:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` whitelist is empty",
                color=0x2b2d31
            )
        )

    parts = []

    if roles:
        role_lines = "\n".join(f"{role.mention} (`{role.id}`)" for role in roles)
        parts.append(f"**Whitelist Roles**\n>>> {role_lines}")

    if users:
        user_lines = "\n".join(f"{user.mention} (`{user.id}`)" for user in users)
        parts.append(f"**Whitelisted Users**\n>>> {user_lines}")

    emb = discord.Embed(
        title="♰ Whitelist",
        description="\n\n".join(parts),
        color=0x2b2d31
    )

    emb.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else bot.user.display_avatar.url)

    now = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"{ctx.guild.name} | Today at : {now}",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@cmd_wl.command(name="add")
@commands.has_permissions(administrator=True)
async def cmd_wl_add(ctx, target: Union[discord.Role, discord.Member] = None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if not target:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}wl add @role` or `{prefix}wl add @user`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg.setdefault("automod_whitelist_role_ids", [])
    cfg.setdefault("automod_whitelist_user_ids", [])

    if isinstance(target, discord.Role):
        if target.id in cfg["automod_whitelist_role_ids"]:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description=f"`❌` {target.mention} is already whitelisted",
                    color=0x2b2d31
                )
            )

        cfg["automod_whitelist_role_ids"].append(target.id)
        save_config()

        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`✅` added role to whitelist: {target.mention}",
                color=0x2b2d31
            )
        )

    if isinstance(target, discord.Member):
        if target.id in cfg["automod_whitelist_user_ids"]:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description=f"`❌` {target.mention} is already whitelisted",
                    color=0x2b2d31
                )
            )

        cfg["automod_whitelist_user_ids"].append(target.id)
        save_config()

        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`✅` added user to whitelist: {target.mention}",
                color=0x2b2d31
            )
        )


@cmd_wl.command(name="remove")
@commands.has_permissions(administrator=True)
async def cmd_wl_remove(ctx, target: Union[discord.Role, discord.Member] = None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if not target:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}wl remove @role` or `{prefix}wl remove @user`",
                color=0x2b2d31
            )
        )

    cfg = get_guild_config(ctx.guild.id)
    cfg.setdefault("automod_whitelist_role_ids", [])
    cfg.setdefault("automod_whitelist_user_ids", [])

    if isinstance(target, discord.Role):
        if target.id not in cfg["automod_whitelist_role_ids"]:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description=f"`❌` {target.mention} is not in whitelist",
                    color=0x2b2d31
                )
            )

        cfg["automod_whitelist_role_ids"].remove(target.id)
        save_config()

        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`✅` removed role from whitelist: {target.mention}",
                color=0x2b2d31
            )
        )

    if isinstance(target, discord.Member):
        if target.id not in cfg["automod_whitelist_user_ids"]:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description=f"`❌` {target.mention} is not in whitelist",
                    color=0x2b2d31
                )
            )

        cfg["automod_whitelist_user_ids"].remove(target.id)
        save_config()

        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`✅` removed user from whitelist: {target.mention}",                color=0x2b2d31
            )
        )

@bot.command(name="backup")
@commands.has_permissions(administrator=True)
async def cmd_backup(ctx, name=None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if not name:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}backup name`",
                color=0x2b2d31
            )
        )

    await backup_guild_structure(ctx.guild, name)

    cfg = get_guild_config(ctx.guild.id)
    log_channel_id = cfg.get("log_channel_id")

    if log_channel_id:
        log_channel = ctx.guild.get_channel(int(log_channel_id))
        if log_channel:
            now = ph_now().strftime("%I:%M %p")

            log_emb = discord.Embed(
                title="📦 Backup Created",
                color=0x5865f2
            )

            log_emb.add_field(name="Name", value=f"`{name}`", inline=False)
            log_emb.add_field(name="File", value=f"`{BACKUPS_FILE}`", inline=False)
            log_emb.add_field(name="Server", value=f"`{ctx.guild.name}`", inline=False)
            log_emb.add_field(name="User", value=ctx.author.mention, inline=False)

            log_emb.set_footer(
                text=f"Today at : {now}",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
            )

            try:
                await fallen_safe_send(log_channel, embed=log_emb)
            except Exception:
                pass

    emb = discord.Embed(
        title="♰ Backup Created",
        color=0x2b2d31
    )

    emb.add_field(
        name="Status",
        value="`✅` backup created",
        inline=False
    )

    emb.add_field(
        name="Name",
        value=f"`{name}`",
        inline=False
    )

    emb.add_field(
        name="File",
        value=f"`{BACKUPS_FILE}`",
        inline=False
    )

    emb.add_field(
        name="Server",
        value=f"{ctx.guild.name}",
        inline=False
    )

    emb.add_field(
        name="User",
        value=ctx.author.mention,
        inline=False
    )

    emb.set_thumbnail(
        url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
    )

    now = ph_now().strftime("%I:%M %p")

    emb.set_footer(
        text=f"{ctx.guild.name} | Today at : {now}",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="loadbackup")
@commands.has_permissions(administrator=True)
async def cmd_loadbackup(ctx, name=None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if not name:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}loadbackup name`",
                color=0x2b2d31
            )
        )

    data = server_backups.get(name)
    if not data:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` backup not found",
                color=0x2b2d31
            )
        )

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` can't find my bot in this server",
                color=0x2b2d31
            )
        )

    needed = [
        me.guild_permissions.manage_roles,
        me.guild_permissions.manage_channels,
        me.guild_permissions.manage_guild
    ]

    if not all(needed):
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` i need `Manage Roles`, `Manage Channels`, and `Manage Server` permissions",
                color=0x2b2d31
            )
        )

    status = await ctx.send(embed=discord.Embed(
        description=f"`⏳` loading backup `{name}`...",
        color=0x2b2d31
    ))

    delete_tasks = []
    for channel in list(ctx.guild.channels):
        delete_tasks.append(channel.delete(reason="Fast clean restore"))

    await asyncio.gather(*delete_tasks, return_exceptions=True)

    role_map = await restore_roles(ctx.guild, data.get("roles", []))
    category_map = await restore_categories(ctx.guild, data.get("categories", []), role_map)
    await restore_channels(ctx.guild, data.get("channels", []), category_map, role_map)

    cfg = get_guild_config(ctx.guild.id)
    log_channel_id = cfg.get("log_channel_id")

    if log_channel_id:
        log_channel = ctx.guild.get_channel(int(log_channel_id))
        if log_channel:
            now = ph_now().strftime("%I:%M %p")

            log_emb = discord.Embed(
                title="📦 Backup Loaded",
                color=0x57f287
            )

            log_emb.add_field(name="Name", value=f"`{name}`", inline=False)
            log_emb.add_field(name="File", value=f"`{BACKUPS_FILE}`", inline=False)
            log_emb.add_field(name="Server", value=f"`{ctx.guild.name}`", inline=False)
            log_emb.add_field(name="User", value=ctx.author.mention, inline=False)

            log_emb.set_footer(
                text=f"Today at : {now}",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
            )

            try:
                await fallen_safe_send(log_channel, embed=log_emb)
            except Exception:
                pass

    await status.edit(embed=discord.Embed(
        description=f"`✅` server restored from `{name}`",
        color=0x2b2d31
    ))


@bot.command(name="backuplist")
@commands.has_permissions(administrator=True)
async def cmd_backuplist(ctx):
    if not server_backups:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` no backups found",
                color=0x2b2d31
            )
        )

    lines = []
    for name, data in server_backups.items():
        created = data.get("created_at", "unknown")
        source = data.get("guild_name", "unknown")
        lines.append(f"`{name}` - {source} ({created})")

    emb = discord.Embed(
        title="♰ Server Backups",
        description=">>> " + "\n".join(lines),
        color=0x2b2d31
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="deletebackup")
@commands.has_permissions(administrator=True)
async def cmd_deletebackup(ctx, name=None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if not name:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"`❌` use: `{prefix}deletebackup name`",
                color=0x2b2d31
            )
        )

    if name not in server_backups:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="`❌` backup not found",
                color=0x2b2d31
            )
        )

    server_backups.pop(name, None)
    await save_json(BACKUPS_FILE, server_backups)

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description=f"`✅` deleted backup `{name}`",
            color=0x2b2d31
        )
    )

@bot.tree.command(name="wcstatus", description="show welcome / leave status")
async def slash_wcstatus(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)

    welcome_ch = interaction.guild.get_channel(int(cfg["welcome_channel_id"])) if cfg.get("welcome_channel_id") else None
    leave_ch = interaction.guild.get_channel(int(cfg["leave_channel_id"])) if cfg.get("leave_channel_id") else None
    welcome_msg_ch = interaction.guild.get_channel(int(cfg["welcome_message_channel_id"])) if cfg.get("welcome_message_channel_id") else None
    leave_msg_ch = interaction.guild.get_channel(int(cfg["leave_message_channel_id"])) if cfg.get("leave_message_channel_id") else None

    emb = discord.Embed(
        title="♰ Welcome / Leave Status",
        color=0x2b2d31
    )

    emb.add_field(
        name="Welcome Embed Channel",
        value=welcome_ch.mention if welcome_ch else "`not set`",
        inline=False
    )
    emb.add_field(
        name="Leave Embed Channel",
        value=leave_ch.mention if leave_ch else "`not set`",
        inline=False
    )
    emb.add_field(
        name="Welcome Message Channel",
        value=welcome_msg_ch.mention if welcome_msg_ch else "`not set`",
        inline=False
    )
    emb.add_field(
        name="Leave Message Channel",
        value=leave_msg_ch.mention if leave_msg_ch else "`not set`",
        inline=False
    )
    emb.add_field(
        name="Welcome Embed Text",
        value=cfg.get("welcome_embed_text", "none")[:1024],
        inline=False
    )
    emb.add_field(
        name="Leave Embed Text",
        value=cfg.get("leave_embed_text", "none")[:1024],
        inline=False
    )
    emb.add_field(
        name="Welcome Message Text",
        value=cfg.get("welcome_message_text", "none")[:1024],
        inline=False
    )
    emb.add_field(
        name="Leave Message Text",
        value=cfg.get("leave_message_text", "none")[:1024],
        inline=False
    )

    await interaction.response.send_message(embed=emb, ephemeral=True)


@bot.tree.command(name="setwelcome", description="set welcome embed channel")
@app_commands.describe(channel="Channel for welcome embed")
async def slash_setwelcome(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["welcome_channel_id"] = channel.id
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` welcome embed channel set to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="setleave", description="set leave embed channel")
@app_commands.describe(channel="Channel for leave embed")
async def slash_setleave(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["leave_channel_id"] = channel.id
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` leave embed channel set to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="editwelcome", description="edit welcome embed text")
@app_commands.describe(text="Welcome embed text")
async def slash_editwelcome(interaction: discord.Interaction, text: str):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["welcome_embed_text"] = text
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` welcome embed text updated\n```{text}```",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="editleave", description="edit leave embed text")
@app_commands.describe(text="Leave embed text")
async def slash_editleave(interaction: discord.Interaction, text: str):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["leave_embed_text"] = text
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` leave embed text updated\n```{text}```",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="removewc", description="remove welcome embed channel")
async def slash_removewc(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["welcome_channel_id"] = None
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description="`✅` welcome embed channel removed",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="removelv", description="remove leave embed channel")
async def slash_removelv(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["leave_channel_id"] = None
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description="`✅` leave embed channel removed",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="testwelcome", description="test welcome embed")
async def slash_testwelcome(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    channel_id = cfg.get("welcome_channel_id")

    if not channel_id:
        return await interaction.response.send_message("`❌` welcome embed channel is not set", ephemeral=True)

    channel = interaction.guild.get_channel(int(channel_id))
    if not channel:
        return await interaction.response.send_message("`❌` welcome embed channel not found", ephemeral=True)

    text = format_wc_text(
        cfg.get("welcome_embed_text", "welcome {user} to {server_name} wag ka mahiyan mag lapag"),
        member
    )

    emb = build_welcome_embed(member, text)

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` sent test welcome to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )

    await fallen_safe_send(channel, embed=emb)


@bot.tree.command(name="testleave", description="test leave embed")
async def slash_testleave(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    channel_id = cfg.get("leave_channel_id")

    if not channel_id:
        return await interaction.response.send_message("`❌` leave embed channel is not set", ephemeral=True)

    channel = interaction.guild.get_channel(int(channel_id))
    if not channel:
        return await interaction.response.send_message("`❌` leave embed channel not found", ephemeral=True)

    text = format_wc_text(
        cfg.get("leave_embed_text", "bye hanggang sa muling pag kikita kapatid {user} paalam"),
        member
    )

    emb = build_leave_embed(member, text)

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` sent test leave to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )

    await fallen_safe_send(channel, embed=emb)


@bot.tree.command(name="setwelcomemessage", description="set welcome message channel")
@app_commands.describe(channel="Channel for gray welcome message embed")
async def slash_setwelcomemessage(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["welcome_message_channel_id"] = channel.id
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` welcome message channel set to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="setleavemessage", description="set leave message channel")
@app_commands.describe(channel="Channel for gray leave message embed")
async def slash_setleavemessage(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["leave_message_channel_id"] = channel.id
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` leave message channel set to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="editwelcomemessage", description="edit welcome message text")
@app_commands.describe(text="Welcome message text")
async def slash_editwelcomemessage(interaction: discord.Interaction, text: str):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["welcome_message_text"] = text
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` welcome message text updated\n```{text}```",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="editleavemessage", description="edit leave message text")
@app_commands.describe(text="Leave message text")
async def slash_editleavemessage(interaction: discord.Interaction, text: str):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["leave_message_text"] = text
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` leave message text updated\n```{text}```",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="removewcmsg", description="remove welcome message channel")
async def slash_removewcmsg(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["welcome_message_channel_id"] = None
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description="`✅` welcome message channel removed",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="removelvmsg", description="remove leave message channel")
async def slash_removelvmsg(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    cfg["leave_message_channel_id"] = None
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description="`✅` leave message channel removed",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="testwelcomemessage", description="test welcome message embed")
async def slash_testwelcomemessage(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    channel_id = cfg.get("welcome_message_channel_id")

    if not channel_id:
        return await interaction.response.send_message("`❌` welcome message channel is not set", ephemeral=True)

    channel = interaction.guild.get_channel(int(channel_id))
    if not channel:
        return await interaction.response.send_message("`❌` welcome message channel not found", ephemeral=True)

    text = format_wc_text(
        cfg.get("welcome_message_text", "welcome pokpok {user}"),
        member
    )

    emb = build_gray_message_embed(text)

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` sent test welcome message to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )

    await fallen_safe_send(channel, embed=emb)


@bot.tree.command(name="testleavemessage", description="test leave message embed")
async def slash_testleavemessage(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggggkk", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    channel_id = cfg.get("leave_message_channel_id")

    if not channel_id:
        return await interaction.response.send_message("`❌` leave message channel is not set", ephemeral=True)

    channel = interaction.guild.get_channel(int(channel_id))
    if not channel:
        return await interaction.response.send_message("`❌` leave message channel not found", ephemeral=True)

    text = format_wc_text(
        cfg.get("leave_message_text", "paalam {user}"),
        member
    )

    emb = build_gray_message_embed(text)

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` sent test leave message to {channel.mention}",
            color=0x2b2d31
        ),
        ephemeral=True
    )

    await fallen_safe_send(channel, embed=emb)


class HelpSelect(discord.ui.Select):
    def __init__(self, ps_prefix: str, util_prefix: str):
        self.ps_prefix = ps_prefix
        self.util_prefix = util_prefix

        options = [
            discord.SelectOption(
                label="Partnership",
                value="partnership",
                description="Ps commands",
                emoji="🤝"
            ),
            discord.SelectOption(
                label="Utility",
                value="utility",
                description="Info and utility commands",
                emoji="🏴‍☠️"
            ),
            discord.SelectOption(
                label="Moderation",
                value="moderation",
                description="Moderation commands",
                emoji="⚙️"
            ),
            discord.SelectOption(
                label="Autoresponder",
                value="autoresponder",
                description="Custom auto replies",
                emoji="☠️"
            ),
            discord.SelectOption(
                label="Backup",
                value="backup",
                description="Server backup and restore",
                emoji="📂"
            ),
            discord.SelectOption(
                label="Anti Nuke",
                value="antinuke",
                description="Anti nuke commands",
                emoji="🛡️"
            ),
            discord.SelectOption(
                label="Welcome / Leave",
                value="welcomer",
                description="Welcome and leave setup",
                emoji="🙋‍♂️"
            ),
        ]

        super().__init__(
            placeholder="select help category",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]

        emb = discord.Embed(color=0x2b2d31)

        if interaction.client.user:
            emb.set_author(
                name=f"{interaction.client.user.name} commands",
                icon_url=interaction.client.user.display_avatar.url
            )
            emb.set_thumbnail(url=interaction.client.user.display_avatar.url)

        if category == "partnership":
            emb.description = (
                "♰ 𝗣𝗮𝗿𝘁𝗻𝗲𝗿𝘀𝗵𝗶𝗽\n"
                f">>> `{self.ps_prefix}setup #channel @manager @partner`\n"
                f"`{self.ps_prefix}stat`\n"
                f"`{self.ps_prefix}list`\n"
                f"`{self.ps_prefix}remove @user`\n"
                f"`{self.ps_prefix}prefix <newprefix>`\n"
                f"`{self.ps_prefix}setad <server ad>`\n"
                f"`{self.ps_prefix}ap @user 10`\n"
                f"`{self.ps_prefix}rmp @user 10`"
            )

        elif category == "utility":
            emb.description = (
                "♰ 𝗨𝘁𝗶𝗹𝗶𝘁𝘆\n"
                f">>> `{self.util_prefix}av @user`\n"
                f"`{self.util_prefix}bn @user`\n"
                f"`{self.util_prefix}userinfo @user` / `{self.util_prefix}ui @user`\n"
                f"`{self.util_prefix}serverinfo` / `{self.util_prefix}si`\n"
                f"`{self.util_prefix}roleinfo @role` / `{self.util_prefix}ri @role`\n"
                f"`{self.util_prefix}botinfo` / `{self.util_prefix}bi`\n"
                f"`{self.util_prefix}role @user @role`\n"
                f"`{self.util_prefix}sticky message`\n"
                f"`{self.util_prefix}unsticky`\n"
                f"`{self.util_prefix}prefix <newprefix>`"
            )

        elif category == "moderation":
            emb.description = (
                "♰ 𝗠𝗼𝗱𝗲𝗿𝗮𝘁𝗶𝗼𝗻\n"
                f">>> `{self.util_prefix}ban @user [reason]`\n"
                f"`{self.util_prefix}unban user_id [reason]`\n"
                f"`{self.util_prefix}kick @user [reason]`\n"
                f"`{self.util_prefix}timeout @user 1m/1h/1d [reason]`\n"
                f"`{self.util_prefix}untimeout @user [reason]`\n"
                f"`{self.util_prefix}lock`\n"
                f"`{self.util_prefix}unlock`\n"
                f"`{self.util_prefix}afk [reason]`\n"
                f"`{self.util_prefix}snipe [1-10]`"
            )

        elif category == "autoresponder":
            emb.description = (
                "♰ 𝗔𝘂𝘁𝗼𝗿𝗲𝘀𝗽𝗼𝗻𝗱𝗲𝗿\n"
                f">>> `{self.util_prefix}autoresponder on/off`\n"
                f"`{self.util_prefix}autoresponder add trigger | reply`\n"
                f"`{self.util_prefix}autoresponder remove trigger`\n"
                f"`{self.util_prefix}autoresponder list`"
            )

        elif category == "welcomer":
           emb.description = (
               "♰ 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 / 𝗟𝗲𝗮𝘃𝗲\n"
               f">>> `{self.util_prefix}setwelcome #channel`\n"
               f"`{self.util_prefix}setleave #channel`\n"
               f"`{self.util_prefix}editwelcome <text>`\n"
               f"`{self.util_prefix}editleave <text>`\n"
               f"`{self.util_prefix}removewc`\n"
               f"`{self.util_prefix}removelv`\n"
               f"`{self.util_prefix}testwelcome`\n"
               f"`{self.util_prefix}testleave`\n\n"
               f"`{self.util_prefix}setwelcomemessage #channel`\n"
               f"`{self.util_prefix}setleavemessage #channel`\n"
               f"`{self.util_prefix}editwelcomemessage <text>`\n"
               f"`{self.util_prefix}editleavemessage <text>`\n"
               f"`{self.util_prefix}removewcmsg`\n"
               f"`{self.util_prefix}removelvmsg`\n"
               f"`{self.util_prefix}testwelcomemessage`\n"
               f"`{self.util_prefix}testleavemessage`\n\n"
               f"`{self.util_prefix}wcstatus`"
           )

        elif category == "backup":
            emb.description = (
                "♰ 𝗕𝗮𝗰𝗸𝘂𝗽\n"
                f">>> `{self.util_prefix}backup name`\n"
                f"`{self.util_prefix}loadbackup name`\n"
                f"`{self.util_prefix}backuplist`\n"
                f"`{self.util_prefix}deletebackup name`"
            )

        elif category == "antinuke":
            emb.description = (
                "♰ 𝗔𝗻𝘁𝗶 𝗡𝘂𝗸𝗲\n"
                f">>> `{self.util_prefix}anti on/off`\n"
                f"`{self.util_prefix}anti status` / `{self.util_prefix}as`\n"
                f"`{self.util_prefix}automod on/off`\n"
                f"`{self.util_prefix}antilink on/off`\n"
                f"`{self.util_prefix}antispam on/off`\n"
                f"`{self.util_prefix}automodlogs #channel`\n\n"
                f"`{self.util_prefix}wl add @role/@user`\n"
                f"`{self.util_prefix}wl remove @role/@user`\n"
                f"`{self.util_prefix}wl list`\n\n"
                f"`{self.util_prefix}anti channel on/off`\n"
                f"`{self.util_prefix}anti role on/off`\n"
                f"`{self.util_prefix}anti webhook on/off`\n"
                f"`{self.util_prefix}anti botadd on/off`\n"
                f"`{self.util_prefix}anti channeldelete on/off`\n"
                f"`{self.util_prefix}anti admin on/off`\n"
                f"`{self.util_prefix}anti massban on/off` / `{self.util_prefix}anti mb on/off`\n"
                f"`{self.util_prefix}anti masskick on/off` / `{self.util_prefix}anti mk on/off`\n"
                f"`{self.util_prefix}anti channel rename` / `{self.util_prefix}anti crename`\n"
                f"`{self.util_prefix}anti server rename` / `{self.util_prefix}anti srename`\n"
                f"`{self.util_prefix}antiinteraction on/off`\n\n"


                f"`{self.util_prefix}set punishment ban/kick`"
            )


        emb.set_footer(text=f"01 = {self.ps_prefix} | 02 = {self.util_prefix}")
        await interaction.response.edit_message(embed=emb, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, ps_prefix: str, util_prefix: str):
        super().__init__(timeout=180)
        self.add_item(HelpSelect(ps_prefix, util_prefix))


async def send_4t_help(channel, guild, requester):
    if not guild:
        return await fallen_safe_send(channel, content="server only")

    guild_cfg = get_guild_config(guild.id)
    ps_prefix = guild_cfg.get("ps_prefix", "ps ").strip()
    util_prefix = guild_cfg.get("util_prefix", ",")

    now_text = ph_now().strftime("%I:%M %p")

    emb = discord.Embed(
        description=(
            "♰ 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀\n\n"
            "- Select a category below to view commands\n\n"
            "♰ 𝗖𝗮𝘁𝗲𝗴𝗼𝗿𝗶𝗲𝘀\n\n"
            "- Partnership\n"
            "- Utility\n"
            "- Moderation\n"
            "- Autoresponder\n"
            "- Backup\n"
            "- Anti Nuke\n"
            "- Welcome / Leave\n\n"
            "♰ 𝗣𝗿𝗲𝗳𝗶𝘅𝗲𝘀\n"
            f"- 01 = {ps_prefix}\n"
            f"- 02 = {util_prefix}"
        ),
        color=0x2b2d31
    )

    if bot.user:
        emb.set_author(
            name=f"{bot.user.name} commands",
            icon_url=bot.user.display_avatar.url
        )
        emb.set_thumbnail(url=bot.user.display_avatar.url)

    emb.set_footer(
        text=f"Requested by {requester} | Today at : {now_text}",
        icon_url=requester.display_avatar.url
    )

    view = HelpView(ps_prefix, util_prefix)
    await fallen_safe_send(channel, embed=emb, view=view)


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def cmd_ban(ctx, target=None, *, reason=None):
    if not target:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ use: `,ban @user/user_id [reason]`",
                color=EMBED_COLOR
            )
        )

    reason = reason or "no reason provided"

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't find my bot in this server",
                color=EMBED_COLOR
            )
        )

    if not me.guild_permissions.ban_members:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ i need `Ban Members` permission",
                color=EMBED_COLOR
            )
        )

    member = resolve_member_from_input(ctx, target)

    if member:
        if member == ctx.author:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description="❌ you can't ban yourself",
                    color=EMBED_COLOR
                )
            )

        if member == ctx.guild.owner:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description="❌ can't ban the server owner",
                    color=EMBED_COLOR
                )
            )

        if member.top_role >= me.top_role:
            return await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description="❌ can't ban that user, their role is higher than mine",
                    color=EMBED_COLOR
                )
            )

        try:
            await member.ban(reason=f"{reason} | by {ctx.author}")
            emb = build_mod_embed(
                guild=ctx.guild,
                action_text="Banned",
                target_text=member.mention,
                target_id=member.id,
                moderator=ctx.author,
                color=0xed4245,
                reason=reason,
                thumb_url=member.display_avatar.url
            )
            await fallen_safe_send(ctx.channel, embed=emb)
        except discord.Forbidden:
            await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description="❌ can't ban that user",
                    color=EMBED_COLOR
                )
            )
        except Exception as e:
            await fallen_safe_send(
                ctx.channel,
                embed=discord.Embed(
                    description=f"❌ error: `{e}`",
                    color=EMBED_COLOR
                )
            )
        return

    if not str(target).isdigit():
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ use a valid mention or user id",
                color=EMBED_COLOR
            )
        )

    user_id = int(target)

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.ban(discord.Object(id=user_id), reason=f"{reason} | by {ctx.author}")

        emb = build_mod_embed(
            guild=ctx.guild,
            action_text="Banned",
            target_text=f"`{user}`",
            target_id=user_id,
            moderator=ctx.author,
            color=0xed4245,
            reason=reason,
            thumb_url=user.display_avatar.url
        )
        await fallen_safe_send(ctx.channel, embed=emb)

    except discord.Forbidden:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't ban that user",
                color=EMBED_COLOR
            )
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ error: `{e}`",
                color=EMBED_COLOR
            )
        )


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def cmd_unban(ctx, user_id: int = None, *, reason=None):
    if not user_id:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ use: `,unban user_id [reason]`",
                color=EMBED_COLOR
            )
        )

    reason = reason or "no reason provided"

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't find my bot in this server",
                color=EMBED_COLOR
            )
        )

    if not me.guild_permissions.ban_members:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ i need `Ban Members` permission",
                color=EMBED_COLOR
            )
        )

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"{reason} | by {ctx.author}")

        emb = build_mod_embed(
            guild=ctx.guild,
            action_text="Unbanned",
            target_text=f"`{user}`",
            target_id=user_id,
            moderator=ctx.author,
            color=0x57f287,
            reason=reason,
            thumb_url=user.display_avatar.url
        )
        await fallen_safe_send(ctx.channel, embed=emb)

    except discord.NotFound:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ user not found in ban list",
                color=EMBED_COLOR
            )
        )
    except discord.Forbidden:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't unban that user",
                color=EMBED_COLOR
            )
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ error: `{e}`",
                color=EMBED_COLOR
            )
        )


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def cmd_kick(ctx, target=None, *, reason=None):
    if not target:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ use: `,kick @user/user_id [reason]`",
                color=EMBED_COLOR
            )
        )

    reason = reason or "no reason provided"

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't find my bot in this server",
                color=EMBED_COLOR
            )
        )

    if not me.guild_permissions.kick_members:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ i need `Kick Members` permission",
                color=EMBED_COLOR
            )
        )

    member = resolve_member_from_input(ctx, target)

    if not member:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ user must be in this server to kick",
                color=EMBED_COLOR
            )
        )

    if member == ctx.author:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ you can't kick yourself",
                color=EMBED_COLOR
            )
        )

    if member == ctx.guild.owner:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't kick the server owner",
                color=EMBED_COLOR
            )
        )

    if member.top_role >= me.top_role:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't kick that user, their role is higher than mine",
                color=EMBED_COLOR
            )
        )

    try:
        await member.kick(reason=f"{reason} | by {ctx.author}")

        emb = build_mod_embed(
            guild=ctx.guild,
            action_text="Kicked",
            target_text=member.mention,
            target_id=member.id,
            moderator=ctx.author,
            color=0xed4245,
            reason=reason,
            thumb_url=member.display_avatar.url
        )
        await fallen_safe_send(ctx.channel, embed=emb)

    except discord.Forbidden:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't kick that user",
                color=EMBED_COLOR
            )
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ error: `{e}`",
                color=EMBED_COLOR
            )
        )


@bot.command(name="timeout", aliases=["to"])
@commands.has_permissions(moderate_members=True)
async def cmd_timeout(ctx, target=None, duration: str = None, *, reason=None):
    if not target or not duration:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ use: `,timeout @user/user_id 1m/1h/1d [reason]`",
                color=EMBED_COLOR
            )
        )

    reason = reason or "no reason provided"

    delta = parse_timeout_duration(duration)
    if delta is None:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ invalid duration. use `1m`, `1h`, or `1d`",
                color=EMBED_COLOR
            )
        )

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't find my bot in this server",
                color=EMBED_COLOR
            )
        )

    if not me.guild_permissions.moderate_members:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ i need `Moderate Members` permission",
                color=EMBED_COLOR
            )
        )

    member = resolve_member_from_input(ctx, target)

    if not member:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ user must be in this server to timeout",
                color=EMBED_COLOR
            )
        )

    if member == ctx.author:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ you can't timeout yourself",
                color=EMBED_COLOR
            )
        )

    if member == ctx.guild.owner:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't timeout the server owner",
                color=EMBED_COLOR
            )
        )

    if member.top_role >= me.top_role:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't timeout that user, their role is higher than mine",
                color=EMBED_COLOR
            )
        )

    try:
        until = discord.utils.utcnow() + delta
        await member.timeout(until, reason=f"{reason} | by {ctx.author}")

        emb = build_mod_embed(
            guild=ctx.guild,
            action_text="Timed out",
            target_text=member.mention,
            target_id=member.id,
            moderator=ctx.author,
            color=0xed4245,
            reason=reason,
            duration_text=format_duration_text(duration),
            thumb_url=member.display_avatar.url
        )
        await fallen_safe_send(ctx.channel, embed=emb)

    except discord.Forbidden:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't timeout that user",
                color=EMBED_COLOR
            )
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ error: `{e}`",
                color=EMBED_COLOR
            )
        )


@bot.command(name="untimeout", aliases=["unto"])
@commands.has_permissions(moderate_members=True)
async def cmd_untimeout(ctx, target=None, *, reason=None):
    if not target:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ use: `,untimeout @user/user_id [reason]`",
                color=EMBED_COLOR
            )
        )

    reason = reason or "no reason provided"

    me = ctx.guild.me or ctx.guild.get_member(bot.user.id)
    if not me:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't find my bot in this server",
                color=EMBED_COLOR
            )
        )

    if not me.guild_permissions.moderate_members:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ i need `Moderate Members` permission",
                color=EMBED_COLOR
            )
        )

    member = resolve_member_from_input(ctx, target)

    if not member:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ user must be in this server to untimeout",
                color=EMBED_COLOR
            )
        )

    if member.top_role >= me.top_role:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't untimeout that user, their role is higher than mine",
                color=EMBED_COLOR
            )
        )

    try:
        await member.timeout(None, reason=f"{reason} | by {ctx.author}")

        emb = build_mod_embed(
            guild=ctx.guild,
            action_text="Untimed out",
            target_text=member.mention,
            target_id=member.id,
            moderator=ctx.author,
            color=0x57f287,
            reason=reason,
            thumb_url=member.display_avatar.url
        )
        await fallen_safe_send(ctx.channel, embed=emb)

    except discord.Forbidden:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ can't untimeout that user",
                color=EMBED_COLOR
            )
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ error: `{e}`",
                color=EMBED_COLOR
            )
        )


@bot.command(name="sticky")
@commands.has_permissions(manage_messages=True)
async def cmd_sticky(ctx, *, message=None):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    if not message:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ use: `{prefix}sticky message`",
                color=EMBED_COLOR
            )
        )

    cid = ctx.channel.id

    if cid in sticky_messages:
        try:
            old = await ctx.channel.fetch_message(sticky_messages[cid]["msg_id"])
            await old.delete()
        except:
            pass

    sent = await ctx.send(message)

    sticky_messages[cid] = {
        "content": message,
        "msg_id": sent.id
    }

    try:
        await ctx.message.delete()
    except:
        pass


@bot.command(name="lock", aliases=["lockdown"])
@commands.has_permissions(manage_channels=True)
async def cmd_lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel

    overwrite = channel.overwrites_for(ctx.guild.default_role)

    if overwrite.send_messages is False:
        return await fallen_safe_send(
            ctx.channel,
            content=f"🔒 already locked {channel.mention}"
        )

    try:
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await fallen_safe_send(
            ctx.channel,
            content=f"🔒 locked {channel.mention}"
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            content=f"❌ failed to lock {channel.mention}: {e}"
        )


@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def cmd_unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel

    overwrite = channel.overwrites_for(ctx.guild.default_role)

    if overwrite.send_messages is None:
        return await fallen_safe_send(
            ctx.channel,
            content=f"🔓 already unlocked {channel.mention}"
        )

    try:
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await fallen_safe_send(
            ctx.channel,
            content=f"🔓 unlocked {channel.mention}"
        )
    except Exception as e:
        await fallen_safe_send(
            ctx.channel,
            content=f"❌ failed to unlock {channel.mention}: {e}"
        )


@bot.command(name="unsticky")
@commands.has_permissions(manage_messages=True)
async def cmd_unsticky(ctx):
    prefix = get_guild_config(ctx.guild.id).get("util_prefix", ",")

    cid = ctx.channel.id

    if cid not in sticky_messages:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ use: `{prefix}sticky message` first",
                color=EMBED_COLOR
            )
        )

    try:
        old = await ctx.channel.fetch_message(sticky_messages[cid]["msg_id"])
        await old.delete()
    except:
        pass

    sticky_messages.pop(cid, None)

    await fallen_safe_send(
        ctx.channel,
        embed=discord.Embed(
            description="✅ sticky removed",
            color=0x57f287
        )
    )


@bot.command(name="addpoints", aliases=["ap"])
async def cmd_ps_addpoints(ctx, target=None, amount: int = None):

    guild_cfg = get_guild_config(ctx.guild.id)
    ps_prefix = guild_cfg.get("ps_prefix", "ps ").strip()

    used_prefix = ctx.prefix.strip()

    if used_prefix != ps_prefix:
        return

    if ctx.author.id != OWNER_ID:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ owner only",
                color=EMBED_COLOR
            )
        )

    if not target or amount is None:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ use: `{ps_prefix}ap @user 10`",
                color=EMBED_COLOR
            )
        )

    if amount <= 0:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ points must be positive",
                color=EMBED_COLOR
            )
        )

    member = None
    user = None

    if isinstance(target, str):
        mention = re.fullmatch(r"<@!?(\d+)>", target)
        if mention:
            uid = int(mention.group(1))
            member = ctx.guild.get_member(uid)
        elif target.isdigit():
            uid = int(target)
            member = ctx.guild.get_member(uid)

    if member:
        user = member
    else:
        try:
            uid = int(target)
            user = await bot.fetch_user(uid)
        except:
            return await fallen_safe_send(
                ctx.channel,
                content="❌ invalid user"
            )

    gid = str(ctx.guild.id)
    uid_str = str(user.id)

    user_points.setdefault(gid, {})
    user_points[gid][uid_str] = user_points[gid].get(uid_str, 0) + amount

    await save_json(POINTS_FILE, user_points)

    emb = discord.Embed(
        title="♰ Points Added",
        color=0x57f287
    )

    emb.add_field(
        name="User",
        value=f"{user.mention if hasattr(user, 'mention') else user}\n`{user.id}`",
        inline=False
    )

    emb.add_field(
        name="Added",
        value=f"`+{amount}`",
        inline=True
    )

    emb.add_field(
        name="Total",
        value=f"`{user_points[gid][uid_str]}`",
        inline=True
    )

    emb.add_field(
        name="Moderator",
        value=ctx.author.mention,
        inline=False
    )

    emb.set_thumbnail(url=user.display_avatar.url)

    now = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"{ctx.guild.name} | Today at : {now}",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.command(name="removepoints", aliases=["rmp", "rm"])
async def cmd_ps_removepoints(ctx, target=None, amount: int = None):

    guild_cfg = get_guild_config(ctx.guild.id)
    ps_prefix = guild_cfg.get("ps_prefix", "ps ").strip()
    used_prefix = ctx.prefix.strip()

    if used_prefix != ps_prefix:
        return

    if ctx.author.id != OWNER_ID:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ owner only",
                color=EMBED_COLOR
            )
        )

    if not target or amount is None:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description=f"❌ use: `{ps_prefix}rmp @user 10`",
                color=EMBED_COLOR
            )
        )

    if amount <= 0:
        return await fallen_safe_send(
            ctx.channel,
            embed=discord.Embed(
                description="❌ amount must be positive",
                color=EMBED_COLOR
            )
        )

    member = None
    user = None

    if isinstance(target, str):
        mention = re.fullmatch(r"<@!?(\d+)>", target)
        if mention:
            uid = int(mention.group(1))
            member = ctx.guild.get_member(uid)
        elif target.isdigit():
            uid = int(target)
            member = ctx.guild.get_member(uid)

    if member:
        user = member
    else:
        try:
            uid = int(target)
            user = await bot.fetch_user(uid)
        except:
            return await fallen_safe_send(
                ctx.channel,
                content="❌ invalid user"
            )

    gid = str(ctx.guild.id)
    uid_str = str(user.id)

    user_points.setdefault(gid, {})
    current = user_points[gid].get(uid_str, 0)

    new_total = max(0, current - amount)
    user_points[gid][uid_str] = new_total

    await save_json(POINTS_FILE, user_points)

    emb = discord.Embed(
        title="♰ Points Removed",
        color=0xed4245
    )

    emb.add_field(
        name="User",
        value=f"{user.mention if hasattr(user, 'mention') else user}\n`{user.id}`",
        inline=False
    )

    emb.add_field(
        name="Removed",
        value=f"`-{amount}`",
        inline=True
    )

    emb.add_field(
        name="Total",
        value=f"`{new_total}`",
        inline=True
    )

    emb.add_field(
        name="Moderator",
        value=ctx.author.mention,
        inline=False
    )

    emb.set_thumbnail(url=user.display_avatar.url)

    now = ph_now().strftime("%I:%M %p")
    emb.set_footer(
        text=f"{ctx.guild.name} | Today at : {now}",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
    )

    await fallen_safe_send(ctx.channel, embed=emb)


@bot.tree.command(name="say", description="send message or embed")
@app_commands.describe(
    message="Message to send",
    embed="Send as embed?",
    reply="Message ID to reply ",
    image="Attach image to embed ",
    tite="Use >>> style in embed?"
)
async def slash_say(
    interaction: discord.Interaction,
    message: str,
    embed: bool = False,
    reply: str = None,
    image: discord.Attachment = None,
    tite: bool = False
):
    if not interaction.guild:
        return await interaction.response.send_message(
            "server only",
            ephemeral=True
        )

    member = interaction.guild.get_member(interaction.user.id)

    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ enggggkk  HAHAHAH ",
            ephemeral=True
        )

    await interaction.response.send_message("sending.....", ephemeral=True)

    try:
        await interaction.delete_original_response()
    except Exception:
        pass

    ref = None

    if reply:
        try:
            msg = await interaction.channel.fetch_message(int(reply))
            ref = msg.to_reference()
        except Exception:
            pass

    if embed:
        desc = message.strip()

        if tite:
            desc = f">>> {desc}"

        emb = discord.Embed(
            description=desc,
            color=EMBED_COLOR
        )

        if image:
            if image.content_type and image.content_type.startswith("image/"):
                emb.set_image(url=image.url)

        await fallen_safe_send(
            interaction.channel,
            embed=emb,
            reference=ref
        )

    else:
        await fallen_safe_send(
            interaction.channel,
            content=message,
            reference=ref
        )
role_group = app_commands.Group(name="role", description="role tools")


@role_group.command(name="reaction", description="create a reaction role message")
@app_commands.describe(
    message="Message to send",
    embed="Send as embed?",
    emoji="Emoji to use",
    role="Role to give when reacted"
)
async def slash_role_reaction(
    interaction: discord.Interaction,
    message: str,
    embed: bool,
    emoji: str,
    role: discord.Role
):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    member = interaction.guild.get_member(interaction.user.id)
    if not member or not member.guild_permissions.administrator:
        return await interaction.response.send_message("❌ enggkkk ", ephemeral=True)

    me = interaction.guild.me or interaction.guild.get_member(bot.user.id)
    if not me:
        return await interaction.response.send_message("`❌` can't find my bot in this server", ephemeral=True)

    if not me.guild_permissions.manage_roles:
        return await interaction.response.send_message("`❌` i need `Manage Roles` permission", ephemeral=True)

    if not me.guild_permissions.add_reactions:
        return await interaction.response.send_message("`❌` i need `Add Reactions` permission", ephemeral=True)

    if role >= me.top_role:
        return await interaction.response.send_message("`❌` that role is higher than my role", ephemeral=True)

    emoji_key = normalize_role_reaction_emoji(emoji)
    reaction_obj = get_reaction_object(bot, emoji_key)

    try:
        if embed:
            sent = await interaction.channel.send(
                embed=discord.Embed(
                    description=message,
                    color=0x2b2d31
                )
            )
        else:
            sent = await interaction.channel.send(message)

        await sent.add_reaction(reaction_obj)

    except Exception as e:
        return await interaction.response.send_message(
            f"`❌` failed to create role reaction: `{e}`",
            ephemeral=True
        )

    cfg = get_guild_config(interaction.guild.id)
    cfg.setdefault("role_reactions", [])

    cfg["role_reactions"].append({
        "channel_id": interaction.channel.id,
        "message_id": sent.id,
        "role_id": role.id,
        "emoji": emoji_key
    })
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=(
                f"`✅` role reaction created\n"
                f"`💬` message id: `{sent.id}`\n"
                f"`😆` emoji: {emoji_key}\n"
                f"`🙆‍♂️` role: {role.mention}"
            ),
            color=0x2b2d31
        ),
        ephemeral=True
    )


bot.tree.add_command(role_group)

@bot.tree.command(name="autoreact", description="set your  auto react emoji")
@app_commands.describe(emoji="Emoji to auto react with on your messages")
async def slash_autoreact(interaction: discord.Interaction, emoji: str):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    emoji_key = normalize_role_reaction_emoji(emoji)
    reaction_obj = get_reaction_object(bot, emoji_key)

    try:
        test_msg = await interaction.channel.send("testing autoreact...")
        await test_msg.add_reaction(reaction_obj)
        try:
            await test_msg.delete()
        except Exception:
            pass
    except Exception as e:
        return await interaction.response.send_message(
            f"`❌` invalid emoji or i can't use that emoji: `{e}`",
            ephemeral=True
        )

    cfg = get_guild_config(interaction.guild.id)
    cfg.setdefault("autoreact_users", {})
    cfg["autoreact_users"][str(interaction.user.id)] = emoji_key
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` autoreact set to {emoji_key}",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="autoreactoff", description="turn off your auto react")
async def slash_autoreactoff(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    users = cfg.setdefault("autoreact_users", {})

    if str(interaction.user.id) not in users:
        return await interaction.response.send_message(
            embed=discord.Embed(
                description="`❌` you don't have autoreact enabled",
                color=0x2b2d31
            ),
            ephemeral=True
        )

    users.pop(str(interaction.user.id), None)
    save_config()

    await interaction.response.send_message(
        embed=discord.Embed(
            description="`✅` autoreact disabled",
            color=0x2b2d31
        ),
        ephemeral=True
    )


@bot.tree.command(name="autoreactstatus", description="check your auto react")
async def slash_autoreactstatus(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("server only", ephemeral=True)

    cfg = get_guild_config(interaction.guild.id)
    users = cfg.setdefault("autoreact_users", {})
    emoji_key = users.get(str(interaction.user.id))

    if not emoji_key:
        return await interaction.response.send_message(
            embed=discord.Embed(
                description="`❌` you don't have autoreact enabled",
                color=0x2b2d31
            ),
            ephemeral=True
        )

    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"`✅` your autoreact emoji is {emoji_key}",
            color=0x2b2d31
        ),
        ephemeral=True
    )

bot.run(TOKEN)