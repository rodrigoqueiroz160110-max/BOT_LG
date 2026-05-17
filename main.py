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


# NOVO REMOVE TEAM
class RemoveTeamSelect(discord.ui.Select):
    def __init__(self):
        data = load_clubs()

        options = []
        for club_key, club in data["clubs"].items():
            options.append(
                discord.SelectOption(
                    label=club.get("name", club_key),
                    value=club_key,
                    description="Delete this team permanently"
                )
            )

        if not options:
            options = [
                discord.SelectOption(
                    label="No teams found",
                    value="none",
                    description="No teams available"
                )
            ]

        super().__init__(
            placeholder="Select a team to remove",
            min_values=1,
            max_values=1,
            options=options[:25],
            disabled=(options[0].value == "none")
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message(
                "Only administrators can use this.",
                ephemeral=True
            )
            return

        club_key = self.values[0]

        data = load_clubs()
        club = data["clubs"].get(club_key)

        if not club:
            await interaction.response.send_message(
                "Team not found.",
                ephemeral=True
            )
            return

        team_name = club["name"]

        del data["clubs"][club_key]
        save_clubs(data)

        embed = make_embed(
            "Team Removed",
            f"**{team_name}** has been removed successfully.",
            discord.Color.red(),
            "Admin Panel"
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

    # NOVO BOTAO
    @discord.ui.button(label="Remove Team", style=discord.ButtonStyle.danger)
    async def remove_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Only administrators can use this.", ephemeral=True)
            return

        embed = make_embed(
            "Remove Team",
            "Select the team you want to delete permanently.",
            discord.Color.red(),
            "Admin Panel"
        )

        await interaction.response.send_message(
            embed=embed,
            view=RemoveTeamView(),
            ephemeral=True
        )


@bot.tree.command(name="painel", description="Open the admin team management panel")
async def painel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("Only administrators can use this command.", ephemeral=True)
        return

    embed = make_embed(
        "Team Management Panel",
        "Use the buttons below to create teams, add managers, remove managers, or remove teams.",
        discord.Color.dark_teal(),
        "Administrator only"
    )
    embed.add_field(name="Add New Team", value="Create a new team in the database.", inline=False)
    embed.add_field(name="Remove Team", value="Delete a team permanently.", inline=False)
    embed.add_field(name="Add New Manager", value="Give a user permission to manage a team.", inline=False)
    embed.add_field(name="Remove Manager", value="Remove a user's permission to manage a team.", inline=False)

    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online as {bot.user}")


bot.run(TOKEN)
