import os  # ← estava faltando esta importação!
import json
from typing import Optional
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

CANAL_ACCEPT_ID = 1511064052548239565
CANAL_RELEASE_ID = 1511064320727978117
CANAL_FREEAGENCY_ID = 1511125222885953756

CLUBS_FILE = "clubs.json"
MAX_PLAYERS_PER_CLUB = 16

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# -----------------------------
# JSON helpers
# -----------------------------

def load_clubs() -> dict:
    if not os.path.exists(CLUBS_FILE):
        return {"clubs": {}}

    with open(CLUBS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "clubs" not in data:
        data = {"clubs": data}

    return data


def save_clubs(data: dict):
    with open(CLUBS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def normalize_club_name(name: str) -> str:
    return name.strip().lower()


def get_club(club_name: str) -> Optional[dict]:
    data = load_clubs()
    return data["clubs"].get(normalize_club_name(club_name))


def find_manager_club(manager_id: int) -> tuple[Optional[str], Optional[dict]]:
    data = load_clubs()
    for club_key, club in data["clubs"].items():
        if manager_id in club.get("managers", []):
            return club_key, club
    return None, None


def find_player_club(player_id: int) -> tuple[Optional[str], Optional[dict]]:
    data = load_clubs()
    for club_key, club in data["clubs"].items():
        if player_id in club.get("players", []):
            return club_key, club
    return None, None


def is_manager_of_club(user_id: int, club_name: str) -> bool:
    club = get_club(club_name)
    if not club:
        return False
    return user_id in club.get("managers", [])


def make_embed(title: str, description: str, color: discord.Color, footer: Optional[str] = None) -> discord.Embed:
    embed = discord.Embed(
        title=f"⚙️ {title}" if "Team" in title or "Management" in title else title,
        description=description,
        color=color
    )
    if footer:
        embed.set_footer(text=f"📌 {footer}")
    else:
        embed.set_footer(text="UFA League System")
    
    # Adiciona timestamp em todas as embeds
    embed.timestamp = datetime.utcnow()
    
    return embed


def is_admin(interaction: discord.Interaction) -> bool:
    return bool(
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )


def get_member_name(guild: Optional[discord.Guild], user_id: int) -> str:
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member.name
    return f"User-{user_id}"


# -----------------------------
# Panel modals/views
# -----------------------------

class AddTeamModal(discord.ui.Modal, title="🏆 Add New Team"):
    club_name = discord.ui.TextInput(
        label="Team Name",
        placeholder="Example: Thunder FC",
        max_length=60
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        data = load_clubs()
        key = normalize_club_name(str(self.club_name))

        if key in data["clubs"]:
            await interaction.response.send_message("⚠️ A team with this name already exists.", ephemeral=True)
            return

        data["clubs"][key] = {
            "name": str(self.club_name).strip(),
            "managers": [],
            "players": []
        }
        save_clubs(data)

        embed = make_embed(
            "✅ Team Created",
            f"**{str(self.club_name).strip()}** has been successfully added to the database.",
            discord.Color.green(),
            "Administrator Action"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RemoveTeamSelect(discord.ui.Select):
    def __init__(self):
        data = load_clubs()

        options = []
        for club_key, club in data["clubs"].items():
            options.append(
                discord.SelectOption(
                    label=club.get("name", club_key),
                    value=club_key,
                    description="🗑️ Permanently delete this team"
                )
            )

        if not options:
            options = [
                discord.SelectOption(
                    label="No Teams Available",
                    value="none",
                    description="There are no teams to remove"
                )
            ]

        super().__init__(
            placeholder="🔽 Select team to delete",
            min_values=1,
            max_values=1,
            options=options[:25],
            disabled=(options[0].value == "none")
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        club_key = self.values[0]

        data = load_clubs()
        club = data["clubs"].get(club_key)

        if not club:
            await interaction.response.send_message("⚠️ Team not found in the database.", ephemeral=True)
            return

        team_name = club.get("name", club_key)

        del data["clubs"][club_key]
        save_clubs(data)

        embed = make_embed(
            "🗑️ Team Removed",
            f"**{team_name}** has been permanently deleted from the database.",
            discord.Color.red(),
            "Administrator Action"
        )
        await interaction.response.edit_message(embed=embed, view=None)


class RemoveTeamView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(RemoveTeamSelect())


class AddManagerSelect(discord.ui.Select):
    def __init__(self, target_user: discord.Member):
        self.target_user = target_user
        data = load_clubs()

        options = []
        for club_key, club in data["clubs"].items():
            options.append(
                discord.SelectOption(
                    label=club.get("name", club_key),
                    value=club_key,
                    description=f"👥 Managers: {len(club.get('managers', []))} | ⚽ Players: {len(club.get('players', []))}/{MAX_PLAYERS_PER_CLUB}"
                )
            )

        super().__init__(
            placeholder="🔽 Select team for this manager",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        data = load_clubs()
        club_key = self.values[0]
        club = data["clubs"].get(club_key)

        if not club:
            await interaction.response.send_message("⚠️ Team not found in the database.", ephemeral=True)
            return

        managers = club.setdefault("managers", [])
        if self.target_user.id not in managers:
            managers.append(self.target_user.id)
            save_clubs(data)

        embed = make_embed(
            "👔 Manager Added",
            f"{self.target_user.mention} has been granted manager permissions for **{club['name']}**.",
            discord.Color.green(),
            "Administrator Action"
        )
        await interaction.response.edit_message(embed=embed, view=None)


class RemoveManagerSelect(discord.ui.Select):
    def __init__(self, target_user: discord.Member):
        self.target_user = target_user
        data = load_clubs()

        options = []
        for club_key, club in data["clubs"].items():
            if target_user.id in club.get("managers", []):
                options.append(
                    discord.SelectOption(
                        label=club.get("name", club_key),
                        value=club_key,
                        description="🔻 Remove manager permissions from this team"
                    )
                )

        if not options:
            options = [discord.SelectOption(label="No Teams Found", value="none", description="This user is not a manager for any team")]

        super().__init__(
            placeholder="🔽 Select team to remove this manager from",
            min_values=1,
            max_values=1,
            options=options[:25],
            disabled=(options[0].value == "none")
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        data = load_clubs()
        club_key = self.values[0]
        club = data["clubs"].get(club_key)

        if not club:
            await interaction.response.send_message("⚠️ Team not found in the database.", ephemeral=True)
            return

        managers = club.setdefault("managers", [])
        if self.target_user.id in managers:
            managers.remove(self.target_user.id)
            save_clubs(data)

        embed = make_embed(
            "👔 Manager Removed",
            f"{self.target_user.mention} has lost manager permissions for **{club['name']}**.",
            discord.Color.orange(),
            "Administrator Action"
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ManagerUserSelect(discord.ui.UserSelect):
    def __init__(self, mode: str):
        self.mode = mode
        placeholder = "👤 Select the user to add as manager" if mode == "add" else "👤 Select the manager to remove"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        target_user = self.values[0]
        if not isinstance(target_user, discord.Member):
            await interaction.response.send_message("⚠️ Please select a valid server member.", ephemeral=True)
            return

        data = load_clubs()
        if not data["clubs"]:
            await interaction.response.send_message("⚠️ Please create at least one team first using the Add Team button.", ephemeral=True)
            return

        view = discord.ui.View(timeout=120)
        if self.mode == "add":
            view.add_item(AddManagerSelect(target_user))
            title = "🎯 Assign Manager Role"
            description = f"Select which team {target_user.mention} will be assigned to manage."
            color = discord.Color.blurple()
        else:
            view.add_item(RemoveManagerSelect(target_user))
            title = "🔻 Revoke Manager Role"
            description = f"Select which team {target_user.mention} should be removed from."
            color = discord.Color.orange()

        await interaction.response.edit_message(
            embed=make_embed(title, description, color, "Administrator Action"),
            view=view
        )


class ManagerUserSelectView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)
        self.add_item(ManagerUserSelect(mode))


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="➕ Add New Team", style=discord.ButtonStyle.green)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return
        await interaction.response.send_modal(AddTeamModal())

    @discord.ui.button(label="🗑️ Remove Team", style=discord.ButtonStyle.danger)
    async def remove_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        embed = make_embed(
            "🗑️ Remove Team",
            "Select the team you wish to permanently delete from the database.",
            discord.Color.red(),
            "Administrator Action"
        )
        await interaction.response.send_message(embed=embed, view=RemoveTeamView(), ephemeral=True)

    @discord.ui.button(label="👔 Add New Manager", style=discord.ButtonStyle.blurple)
    async def add_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        embed = make_embed(
            "👔 Add New Manager",
            "Select the Discord user who will be granted manager permissions for a team.",
            discord.Color.blurple(),
            "Administrator Action"
        )
        await interaction.response.send_message(embed=embed, view=ManagerUserSelectView("add"), ephemeral=True)

    @discord.ui.button(label="🔻 Remove Manager", style=discord.ButtonStyle.red)
    async def remove_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
            return

        embed = make_embed(
            "🔻 Remove Manager",
            "Select the Discord user who should lose their manager permissions.",
            discord.Color.red(),
            "Administrator Action"
        )
        await interaction.response.send_message(embed=embed, view=ManagerUserSelectView("remove"), ephemeral=True)


# -----------------------------
# Contract views
# -----------------------------

class ContractView(discord.ui.View):
    def __init__(self, player_id: int, manager_id: int, club_key: str):
        super().__init__(timeout=None)
        self.player_id = player_id
        self.manager_id = manager_id
        self.club_key = club_key

    @discord.ui.button(label="✅ Accept Contract", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ You are not the intended recipient of this contract offer.", ephemeral=True)
            return

        data = load_clubs()
        club = data["clubs"].get(self.club_key)

        if not club:
            await interaction.response.send_message("⚠️ The team associated with this contract no longer exists.", ephemeral=True)
            return

        if self.manager_id not in club.get("managers", []):
            await interaction.response.send_message("⚠️ The manager who sent this contract no longer has permissions for this team.", ephemeral=True)
            return

        if len(club.get("players", [])) >= MAX_PLAYERS_PER_CLUB:
            await interaction.response.send_message(f"⚠️ This team has reached the maximum capacity of {MAX_PLAYERS_PER_CLUB} players.", ephemeral=True)
            return

        old_club_key, old_club = find_player_club(self.player_id)
        if old_club_key and old_club_key != self.club_key:
            await interaction.response.send_message(
                f"⚠️ You are already signed to **{old_club.get('name', old_club_key)}**. You must leave your current team before joining another.",
                ephemeral=True
            )
            return

        players = club.setdefault("players", [])
        if self.player_id not in players:
            players.append(self.player_id)
            save_clubs(data)

        guild = bot.guilds[0] if bot.guilds else None
        member = guild.get_member(self.player_id) if guild else None
        player_text = member.mention if member else f"User-{self.player_id}"

        channel = bot.get_channel(CANAL_ACCEPT_ID)
        if channel:
            embed = make_embed(
                "📝 Contract Signed",
                f"{player_text} has officially joined **{club['name']}**.",
                discord.Color.green(),
                f"📊 Current Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
            )
            await channel.send(embed=embed)

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=make_embed(
                "✅ Contract Accepted",
                f"You have successfully joined **{club['name']}**.",
                discord.Color.green(),
                f"📊 Current Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
            ),
            view=self
        )

    @discord.ui.button(label="❌ Decline Contract", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ You are not the intended recipient of this contract offer.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=make_embed(
                "❌ Contract Declined",
                "You have declined this contract offer.",
                discord.Color.red()
            ),
            view=self
        )


# -----------------------------
# Commands
# -----------------------------

@bot.tree.command(name="panel", description="⚙️ Open the administrator team management panel")
async def panel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Only administrators can use this command.", ephemeral=True)
        return

    embed = make_embed(
        "⚙️ Team Management System",
        "Use the interactive buttons below to manage teams and manager permissions.",
        discord.Color.dark_teal(),
        "🔒 Administrator Access Only"
    )
    embed.add_field(name="➕ Add New Team", value="Creates a new team entry in the database.", inline=False)
    embed.add_field(name="🗑️ Remove Team", value="Permanently deletes an existing team from the database.", inline=False)
    embed.add_field(name="👔 Add New Manager", value="Grants a user permission to manage a specific team.", inline=False)
    embed.add_field(name="🔻 Remove Manager", value="Revokes a user's permission to manage a specific team.", inline=False)

    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)


@bot.tree.command(name="contract", description="📝 Send a formal contract offer to a player")
@app_commands.describe(user="The player who will receive the contract offer")
async def contract(interaction: discord.Interaction, user: discord.Member):
    club_key, club = find_manager_club(interaction.user.id)

    if not club_key or not club:
        await interaction.response.send_message("❌ You are not registered as a manager for any team.", ephemeral=True)
        return

    players = club.get("players", [])
    if len(players) >= MAX_PLAYERS_PER_CLUB:
        await interaction.response.send_message(
            f"⚠️ **{club['name']}** has reached the maximum roster size of {MAX_PLAYERS_PER_CLUB} players.",
            ephemeral=True
        )
        return

    current_club_key, current_club = find_player_club(user.id)
    if current_club_key:
        await interaction.response.send_message(
            f"⚠️ {user.mention} is already signed to **{current_club.get('name', current_club_key)}**. A player cannot be signed to multiple teams.",
            ephemeral=True
        )
        return

    embed = make_embed(
        "📝 Official Contract Offer",
        f"You have received a contract offer from **{club['name']}** to join their roster.",
        discord.Color.blurple(),
        f"📊 Current Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
    )
    embed.add_field(name="👔 Issuing Manager", value=interaction.user.mention, inline=True)
    embed.add_field(name="🏆 Organization", value=club["name"], inline=True)
    embed.add_field(name="📌 Next Steps", value="Please review the offer below and accept or decline using the buttons provided.", inline=False)

    try:
        await user.send(embed=embed, view=ContractView(user.id, interaction.user.id, club_key))
        await interaction.response.send_message(
            f"✅ Contract offer has been successfully delivered to {user.mention} for **{club['name']}**.",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ Unable to deliver the contract offer. The user may have disabled direct messages from server members.",
            ephemeral=True
        )


@bot.tree.command(name="releaseplayer", description="🗑️ Remove a player from your team roster")
@app_commands.describe(user="The player who will be removed from your team")
async def releaseplayer(interaction: discord.Interaction, user: discord.Member):
    club_key, club = find_manager_club(interaction.user.id)

    if not club_key or not club:
        await interaction.response.send_message("❌ You are not registered as a manager for any team.", ephemeral=True)
        return

    data = load_clubs()
    club = data["clubs"].get(club_key)
    players = club.setdefault("players", [])

    if user.id not in players:
        await interaction.response.send_message(f"⚠️ {user.mention} is not currently on the roster of **{club['name']}**.", ephemeral=True)
        return

    players.remove(user.id)
    save_clubs(data)

    embed = make_embed(
        "🗑️ Player Released from Team",
        f"{user.mention} has been officially released from **{club['name']}**.",
        discord.Color.orange(),
        f"📊 Updated Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
    )

    channel = bot.get_channel(CANAL_RELEASE_ID)
    if channel:
        await channel.send(embed=embed)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="leave", description="🚪 Voluntarily leave your current team")
async def leave(interaction: discord.Interaction):
    club_key, club = find_player_club(interaction.user.id)

    if not club_key or not club:
        await interaction.response.send_message("❌ You are not currently signed to any team.", ephemeral=True)
        return

    data = load_clubs()
    club = data["clubs"].get(club_key)
    players = club.setdefault("players", [])

    if interaction.user.id in players:
        players.remove(interaction.user.id)
        save_clubs(data)

    embed = make_embed(
        "🚪 Player Left Team",
        f"{interaction.user.mention} has voluntarily left **{club['name']}**.",
        discord.Color.orange(),
        f"📊 Updated Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
    )

    channel = bot.get_channel(CANAL_RELEASE_ID)
    if channel:
        await channel.send(embed=embed)

    await interaction.response.send_message(
        embed=make_embed(
            "✅ You Have Left Your Team",
            f"You are no longer a member of **{club['name']}**.",
            discord.Color.orange(),
            f"📊 Updated Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
        ),
        ephemeral=True
    )


@bot.tree.command(name="roster", description="📋 Display the complete roster information for a team")
@app_commands.describe(club="The name of the team to view")
async def roster(interaction: discord.Interaction, club: str):
    selected_club = get_club(club)

    if not selected_club:
        await interaction.response.send_message("❌ No team found with that name. Please verify the team name and try again.", ephemeral=True)
        return

    players = selected_club.get("players", [])
    player_count = len(players)

    if not players:
        roster_text = "*No players have signed with this team yet.*"
    else:
        lines = []
        for player_id in players:
            member = interaction.guild.get_member(player_id) if interaction.guild else None
            lines.append(f"• {member.name if member else f'User-{player_id}'}")
        roster_text = "\n".join(lines)

    embed = discord.Embed(
        title=f"📋 Team Roster: {selected_club['name']}",
        description=f"**Active Players:** `{player_count}/{MAX_PLAYERS_PER_CLUB}`\n\n{roster_text}",
        color=discord.Color.dark_teal()
    )
    embed.set_footer(text="🏆 UFA League Management System")
    embed.timestamp = datetime.utcnow()

    managers = selected_club.get("managers", [])
    if managers:
        manager_names = []
        for manager_id in managers:
            member = interaction.guild.get_member(manager_id) if interaction.guild else None
            manager_names.append(f"• {member.name if member else f'User-{manager_id}'}")
        embed.add_field(name="👔 Management Staff", value="\n".join(manager_names), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="freeagency", description="📢 Broadcast a free agency announcement to recruiters")
@app_commands.describe(
    message="Your free agency statement or recruitment request",
    position="Your preferred playing position (e.g., Striker, Midfielder, Defender, Goalkeeper)"
)
async def freeagency(interaction: discord.Interaction, message: str, position: str):
    channel = bot.get_channel(CANAL_FREEAGENCY_ID)

    if channel is None:
        await interaction.response.send_message("❌ Unable to locate the Free Agency channel. Please notify an administrator.", ephemeral=True)
        return

    embed = make_embed(
        "📢 Free Agency Announcement",
        "A player is currently seeking a team to join.",
        discord.Color.blue(),
        "🏆 UFA League Management System"
    )
    embed.add_field(name="👤 Player", value=interaction.user.mention, inline=True)
    embed.add_field(name="⚽ Position", value=position, inline=True)
    embed.add_field(name="💬 Statement", value=message, inline=False)

    await channel.send(content=interaction.user.mention, embed=embed)
    await interaction.response.send_message("✅ Your free agency announcement has been posted successfully.", ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot is online and authenticated as {bot.user}")
    print(f"📡 Connected to {len(bot.guilds)} guild(s)")
    print(f"🎮 UFA League Bot is ready!")


bot.run(TOKEN)
