# CODIGO COMPLETO ATUALIZADO COM REMOVE TEAM
# (cole aqui o conteúdo abaixo)

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

def make_embed(title: str, description: str, color: discord.Color, footer: Optional[str] = None):
    embed = discord.Embed(title=title, description=description, color=color)
    if footer:
        embed.set_footer(text=footer)
    return embed

def is_admin(interaction: discord.Interaction) -> bool:
    return bool(
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )

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
            discord.Color.green(),
            "Admin Panel"
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
                    description="Remove this team permanently"
                )
            )

        if not options:
            options = [
                discord.SelectOption(
                    label="No teams available",
                    value="none",
                    description="There are no teams to remove"
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

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Add New Team", style=discord.ButtonStyle.green)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddTeamModal())

    @discord.ui.button(label="Remove Team", style=discord.ButtonStyle.red)
    async def remove_team(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    embed = make_embed(
        "Team Management Panel",
        "Use the buttons below to manage teams.",
        discord.Color.dark_teal(),
        "Administrator only"
    )

    embed.add_field(
        name="Add New Team",
        value="Create a new team in the database.",
        inline=False
    )

    embed.add_field(
        name="Remove Team",
        value="Delete an existing team permanently.",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        view=AdminPanelView(),
        ephemeral=True
    )

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online as {bot.user}")

bot.run(TOKEN)
