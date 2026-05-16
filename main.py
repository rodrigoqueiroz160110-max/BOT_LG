import os
import json
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

CANAL_ACCEPT_ID = 1503241511696076831
CANAL_RELEASE_ID = 1503241512819888129
CANAL_FREEAGENCY_ID = 1503241510320341134

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
        title=title,
        description=description,
        color=color
    )
    if footer:
        embed.set_footer(text=footer)
    return embed


def is_admin(interaction: discord.Interaction) -> bool:
    return bool(
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )


# -----------------------------
# Panel modals/views
# -----------------------------

class AddTeamModal(discord.ui.Modal, title="Add New Team"):
    club_name = discord.ui.TextInput(
        label="Team name",
        placeholder="Example: Thunder FC",
        max_length=60
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        data = load_clubs()
        key = normalize_club_name(str(self.club_name))

        if key in data["clubs"]:
            await interaction.response.send_message("This team already exists.", ephemeral=True)
            return

        data["clubs"][key] = {
            "name": str(self.club_name).strip(),
            "managers": [],
            "players": []
        }
        save_clubs(data)

        embed = make_embed(
            "Team Created",
            f"**{str(self.club_name).strip()}** has been added successfully.",
            discord.Color.teal(),
            "Admin Panel"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


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
                    description=f"Managers: {len(club.get('managers', []))} | Players: {len(club.get('players', []))}/{MAX_PLAYERS_PER_CLUB}"
                )
            )

        super().__init__(
            placeholder="Select the team for this manager",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        data = load_clubs()
        club_key = self.values[0]
        club = data["clubs"].get(club_key)

        if not club:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        managers = club.setdefault("managers", [])
        if self.target_user.id not in managers:
            managers.append(self.target_user.id)
            save_clubs(data)

        embed = make_embed(
            "Manager Added",
            f"{self.target_user.mention} is now a manager of **{club['name']}**.",
            discord.Color.green(),
            "This manager can now send contracts and release players."
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
                        description="Remove manager permission from this team"
                    )
                )

        if not options:
            options = [discord.SelectOption(label="No teams found", value="none", description="This user is not a manager")]

        super().__init__(
            placeholder="Select the team to remove this manager from",
            min_values=1,
            max_values=1,
            options=options[:25],
            disabled=(options[0].value == "none")
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        data = load_clubs()
        club_key = self.values[0]
        club = data["clubs"].get(club_key)

        if not club:
            await interaction.response.send_message("Team not found.", ephemeral=True)
            return

        managers = club.setdefault("managers", [])
        if self.target_user.id in managers:
            managers.remove(self.target_user.id)
            save_clubs(data)

        embed = make_embed(
            "Manager Removed",
            f"{self.target_user.mention} is no longer a manager of **{club['name']}**.",
            discord.Color.orange(),
            "This user can no longer send contracts for this team."
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ManagerUserSelect(discord.ui.UserSelect):
    def __init__(self, mode: str):
        self.mode = mode
        placeholder = "Select the new manager" if mode == "add" else "Select the manager to remove"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        target_user = self.values[0]
        if not isinstance(target_user, discord.Member):
            await interaction.response.send_message("Please select a server member.", ephemeral=True)
            return

        data = load_clubs()
        if not data["clubs"]:
            await interaction.response.send_message("Create a team first.", ephemeral=True)
            return

        view = discord.ui.View(timeout=120)
        if self.mode == "add":
            view.add_item(AddManagerSelect(target_user))
            title = "Choose Manager Team"
            description = f"Select which team {target_user.mention} will manage."
            color = discord.Color.blurple()
        else:
            view.add_item(RemoveManagerSelect(target_user))
            title = "Remove Manager"
            description = f"Select which team {target_user.mention} should be removed from."
            color = discord.Color.orange()

        await interaction.response.edit_message(
            embed=make_embed(title, description, color, "Admin Panel"),
            view=view
        )


class ManagerUserSelectView(discord.ui.View):
    def __init__(self, mode: str):
        super().__init__(timeout=120)
        self.add_item(ManagerUserSelect(mode))


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Add New Team", style=discord.ButtonStyle.green)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return
        await interaction.response.send_modal(AddTeamModal())

    @discord.ui.button(label="Add New Manager", style=discord.ButtonStyle.blurple)
    async def add_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        embed = make_embed(
            "Add New Manager",
            "Select the Discord user who will manage a team.",
            discord.Color.blurple(),
            "Admin Panel"
        )
        await interaction.response.send_message(embed=embed, view=ManagerUserSelectView("add"), ephemeral=True)

    @discord.ui.button(label="Remove Manager", style=discord.ButtonStyle.red)
    async def remove_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        embed = make_embed(
            "Remove Manager",
            "Select the Discord user who should lose manager permissions.",
            discord.Color.red(),
            "Admin Panel"
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

    @discord.ui.button(label="Accept Contract", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("This contract is not for you.", ephemeral=True)
            return

        data = load_clubs()
        club = data["clubs"].get(self.club_key)

        if not club:
            await interaction.response.send_message("This team no longer exists.", ephemeral=True)
            return

        if self.manager_id not in club.get("managers", []):
            await interaction.response.send_message("This manager no longer has permission for this team.", ephemeral=True)
            return

        if len(club.get("players", [])) >= MAX_PLAYERS_PER_CLUB:
            await interaction.response.send_message("This team is full: 16/16 players.", ephemeral=True)
            return

        old_club_key, old_club = find_player_club(self.player_id)
        if old_club_key and old_club_key != self.club_key:
            await interaction.response.send_message(
                f"You are already signed to **{old_club.get('name', old_club_key)}**.",
                ephemeral=True
            )
            return

        players = club.setdefault("players", [])
        if self.player_id not in players:
            players.append(self.player_id)
            save_clubs(data)

        guild = bot.guilds[0] if bot.guilds else None
        member = guild.get_member(self.player_id) if guild else None
        player_text = member.mention if member else f"User `{self.player_id}`"

        channel = bot.get_channel(CANAL_ACCEPT_ID)
        if channel:
            embed = make_embed(
                "Contract Accepted",
                f"{player_text} has joined **{club['name']}**.",
                discord.Color.green(),
                f"Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
            )
            await channel.send(embed=embed)

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=make_embed(
                "Welcome to the Team",
                f"You accepted the contract from **{club['name']}**.",
                discord.Color.green(),
                f"Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
            ),
            view=self
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("This contract is not for you.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=make_embed(
                "Contract Declined",
                "You declined this contract offer.",
                discord.Color.red()
            ),
            view=self
        )


# -----------------------------
# Commands
# -----------------------------

@bot.tree.command(name="painel", description="Open the admin team management panel")
async def painel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("Only administrators can use this command.", ephemeral=True)
        return

    embed = make_embed(
        "Team Management Panel",
        "Use the buttons below to create teams, add managers, or remove managers.",
        discord.Color.dark_teal(),
        "Administrator only"
    )
    embed.add_field(name="Add New Team", value="Create a new team in the database.", inline=False)
    embed.add_field(name="Add New Manager", value="Give a user permission to manage a team.", inline=False)
    embed.add_field(name="Remove Manager", value="Remove a user's permission to manage a team.", inline=False)

    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)


@bot.tree.command(name="contract", description="Send a contract offer to a player")
@app_commands.describe(user="Player who will receive the contract")
async def contract(interaction: discord.Interaction, user: discord.Member):
    club_key, club = find_manager_club(interaction.user.id)

    if not club_key or not club:
        await interaction.response.send_message("You are not registered as a manager of any team.", ephemeral=True)
        return

    players = club.get("players", [])
    if len(players) >= MAX_PLAYERS_PER_CLUB:
        await interaction.response.send_message(
            f"**{club['name']}** is full: {len(players)}/{MAX_PLAYERS_PER_CLUB} players.",
            ephemeral=True
        )
        return

    current_club_key, current_club = find_player_club(user.id)
    if current_club_key:
        await interaction.response.send_message(
            f"{user.mention} is already signed to **{current_club.get('name', current_club_key)}**.",
            ephemeral=True
        )
        return

    embed = make_embed(
        "Contract Offer",
        f"You received a contract offer from **{club['name']}**.",
        discord.Color.blurple(),
        f"Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
    )
    embed.add_field(name="Manager", value=interaction.user.mention, inline=True)
    embed.add_field(name="Team", value=club["name"], inline=True)
    embed.add_field(name="Action Required", value="Accept or decline the offer using the buttons below.", inline=False)

    try:
        await user.send(embed=embed, view=ContractView(user.id, interaction.user.id, club_key))
        await interaction.response.send_message(
            f"Contract sent to {user.mention} for **{club['name']}**.",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "I could not send a DM to this user. They may have DMs closed.",
            ephemeral=True
        )


@bot.tree.command(name="releplayer", description="Release a player from your team")
@app_commands.describe(user="Player who will be removed from your team")
async def releplayer(interaction: discord.Interaction, user: discord.Member):
    club_key, club = find_manager_club(interaction.user.id)

    if not club_key or not club:
        await interaction.response.send_message("You are not registered as a manager of any team.", ephemeral=True)
        return

    data = load_clubs()
    club = data["clubs"].get(club_key)
    players = club.setdefault("players", [])

    if user.id not in players:
        await interaction.response.send_message(f"{user.mention} is not in **{club['name']}**.", ephemeral=True)
        return

    players.remove(user.id)
    save_clubs(data)

    embed = make_embed(
        "Player Released",
        f"{user.mention} has been released from **{club['name']}**.",
        discord.Color.orange(),
        f"Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
    )

    channel = bot.get_channel(CANAL_RELEASE_ID)
    if channel:
        await channel.send(embed=embed)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="release", description="Leave your current team")
async def release(interaction: discord.Interaction):
    club_key, club = find_player_club(interaction.user.id)

    if not club_key or not club:
        await interaction.response.send_message("You are not signed to any team.", ephemeral=True)
        return

    data = load_clubs()
    club = data["clubs"].get(club_key)
    players = club.setdefault("players", [])

    if interaction.user.id in players:
        players.remove(interaction.user.id)
        save_clubs(data)

    embed = make_embed(
        "Player Released",
        f"{interaction.user.mention} has left **{club['name']}**.",
        discord.Color.orange(),
        f"Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
    )

    channel = bot.get_channel(CANAL_RELEASE_ID)
    if channel:
        await channel.send(embed=embed)

    await interaction.response.send_message(
        embed=make_embed(
            "You Left the Team",
            f"You are no longer part of **{club['name']}**.",
            discord.Color.orange(),
            f"Roster: {len(players)}/{MAX_PLAYERS_PER_CLUB}"
        ),
        ephemeral=True
    )


@bot.tree.command(name="squad", description="Show the squad sheet of a team")
@app_commands.describe(club="Team name")
async def squad(interaction: discord.Interaction, club: str):
    selected_club = get_club(club)

    if not selected_club:
        await interaction.response.send_message("Team not found.", ephemeral=True)
        return

    players = selected_club.get("players", [])
    player_count = len(players)

    if not players:
        roster = "No players signed yet."
    else:
        lines = []
        for player_id in players:
            member = interaction.guild.get_member(player_id) if interaction.guild else None
            if member:
                lines.append(member.name)
            else:
                lines.append(f"User {player_id}")
        roster = "\n".join(lines)

    embed = discord.Embed(
        title=f"Squadsheet of {selected_club['name']}",
        description=f"**Players:** `{player_count}/{MAX_PLAYERS_PER_CLUB} (max)`\n\n{roster}",
        color=discord.Color.dark_teal()
    )
    embed.set_footer(text="UFA Team Management")

    managers = selected_club.get("managers", [])
    if managers:
        manager_names = []
        for manager_id in managers:
            member = interaction.guild.get_member(manager_id) if interaction.guild else None
            manager_names.append(member.name if member else f"User {manager_id}")
        embed.add_field(name="Managers", value="\n".join(manager_names), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="freeagency", description="Send a free agency post")
@app_commands.describe(
    message="Your free agency message",
    position="Your position"
)
async def freeagency(interaction: discord.Interaction, message: str, position: str):
    channel = bot.get_channel(CANAL_FREEAGENCY_ID)

    if channel is None:
        await interaction.response.send_message("I could not find the Free Agency channel.", ephemeral=True)
        return

    embed = make_embed(
        "New Free Agency",
        "A player is looking for a team.",
        discord.Color.blue(),
        "UFA Team Management"
    )
    embed.add_field(name="Player", value=interaction.user.mention, inline=True)
    embed.add_field(name="Position", value=position, inline=True)
    embed.add_field(name="Message", value=message, inline=False)

    await channel.send(content=interaction.user.mention, embed=embed)
    await interaction.response.send_message("Free agency post sent successfully.", ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online as {bot.user}")


bot.run(TOKEN)
