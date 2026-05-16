import os
import json
import uuid
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

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


# -----------------------------
# Storage
# -----------------------------
def load_clubs():
    if not os.path.exists(CLUBS_FILE):
        return {"clubs": {}}

    with open(CLUBS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "clubs" not in data:
        data["clubs"] = {}

    return data


def save_clubs(data):
    with open(CLUBS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


def make_club_id(name: str) -> str:
    base = normalize_name(name).lower().replace(" ", "-")
    return f"{base}-{uuid.uuid4().hex[:6]}"


def get_club_by_id(club_id: str):
    data = load_clubs()
    return data["clubs"].get(club_id)


def find_club_by_name(name: str):
    target = normalize_name(name).lower()
    data = load_clubs()

    for club_id, club in data["clubs"].items():
        if club["name"].lower() == target:
            return club_id, club

    return None, None


def get_user_clubs(user_id: int):
    data = load_clubs()
    clubs = []

    for club_id, club in data["clubs"].items():
        if str(user_id) in club.get("managers", []):
            clubs.append((club_id, club))

    return clubs


def get_player_club(user_id: int):
    data = load_clubs()

    for club_id, club in data["clubs"].items():
        if str(user_id) in club.get("players", []):
            return club_id, club

    return None, None


def add_player_to_club(user_id: int, club_id: str):
    data = load_clubs()
    club = data["clubs"].get(club_id)

    if club is None:
        return False

    user_key = str(user_id)

    # A player can only be in one club at a time.
    for other_club in data["clubs"].values():
        if user_key in other_club.get("players", []):
            other_club["players"].remove(user_key)

    if user_key not in club["players"]:
        club["players"].append(user_key)

    save_clubs(data)
    return True


def remove_player_from_club(user_id: int, club_id: str):
    data = load_clubs()
    club = data["clubs"].get(club_id)

    if club is None:
        return False

    user_key = str(user_id)

    if user_key in club.get("players", []):
        club["players"].remove(user_key)
        save_clubs(data)
        return True

    return False


def is_admin(interaction: discord.Interaction) -> bool:
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.administrator)


def is_manager_for_club(user_id: int, club_id: str) -> bool:
    club = get_club_by_id(club_id)
    return bool(club and str(user_id) in club.get("managers", []))


async def club_autocomplete(interaction: discord.Interaction, current: str):
    data = load_clubs()
    current_lower = current.lower()

    choices = []
    for club_id, club in data["clubs"].items():
        name = club["name"]
        if current_lower in name.lower():
            choices.append(app_commands.Choice(name=name, value=club_id))

    return choices[:25]


def user_display_without_mention(guild: discord.Guild | None, user_id: str) -> str:
    member = guild.get_member(int(user_id)) if guild else None
    if member:
        return member.name
    return f"user-{user_id}"


# -----------------------------
# Embeds
# -----------------------------
def success_embed(title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )
    embed.set_footer(text="UFA Team System")
    return embed


def info_embed(title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple()
    )
    embed.set_footer(text="UFA Team System")
    return embed


def warning_embed(title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.orange()
    )
    embed.set_footer(text="UFA Team System")
    return embed


def error_embed(title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red()
    )
    embed.set_footer(text="UFA Team System")
    return embed


# -----------------------------
# Admin Panel
# -----------------------------
class AddTeamModal(discord.ui.Modal, title="Add New Team"):
    club_name = discord.ui.TextInput(
        label="Team name",
        placeholder="Example: UFA United",
        max_length=80
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=error_embed("Permission denied", "Only administrators can use this panel."),
                ephemeral=True
            )
            return

        name = normalize_name(str(self.club_name))
        if not name:
            await interaction.response.send_message(
                embed=error_embed("Invalid team name", "Please enter a valid team name."),
                ephemeral=True
            )
            return

        _, existing = find_club_by_name(name)
        if existing:
            await interaction.response.send_message(
                embed=error_embed("Team already exists", f"**{name}** is already registered."),
                ephemeral=True
            )
            return

        data = load_clubs()
        club_id = make_club_id(name)
        data["clubs"][club_id] = {
            "name": name,
            "managers": [],
            "players": []
        }
        save_clubs(data)

        await interaction.response.send_message(
            embed=success_embed("Team created", f"**{name}** has been added successfully."),
            ephemeral=True
        )


class ManagerUserSelect(discord.ui.UserSelect):
    def __init__(self, club_id: str):
        super().__init__(
            placeholder="Select the manager",
            min_values=1,
            max_values=1
        )
        self.club_id = club_id

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=error_embed("Permission denied", "Only administrators can add managers."),
                ephemeral=True
            )
            return

        selected_user = self.values[0]
        data = load_clubs()
        club = data["clubs"].get(self.club_id)

        if club is None:
            await interaction.response.send_message(
                embed=error_embed("Team not found", "This team no longer exists."),
                ephemeral=True
            )
            return

        user_key = str(selected_user.id)
        if user_key not in club["managers"]:
            club["managers"].append(user_key)
            save_clubs(data)

        await interaction.response.send_message(
            embed=success_embed(
                "Manager added",
                f"{selected_user.mention} can now manage **{club['name']}**."
            ),
            ephemeral=True
        )


class ManagerUserSelectView(discord.ui.View):
    def __init__(self, club_id: str):
        super().__init__(timeout=120)
        self.add_item(ManagerUserSelect(club_id))


class TeamSelectForManager(discord.ui.Select):
    def __init__(self):
        data = load_clubs()
        options = []

        for club_id, club in data["clubs"].items():
            options.append(
                discord.SelectOption(
                    label=club["name"][:100],
                    value=club_id,
                    description="Add a manager to this team"
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No teams available",
                    value="none",
                    description="Create a team first"
                )
            )

        super().__init__(
            placeholder="Select a team",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=error_embed("Permission denied", "Only administrators can use this menu."),
                ephemeral=True
            )
            return

        club_id = self.values[0]
        if club_id == "none":
            await interaction.response.send_message(
                embed=warning_embed("No teams found", "Create a team first using **Add New Team**."),
                ephemeral=True
            )
            return

        club = get_club_by_id(club_id)
        await interaction.response.send_message(
            embed=info_embed(
                "Select manager",
                f"Choose the Discord user who will manage **{club['name']}**."
            ),
            view=ManagerUserSelectView(club_id),
            ephemeral=True
        )


class TeamSelectForManagerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(TeamSelectForManager())


class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Add New Team", style=discord.ButtonStyle.green)
    async def add_new_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=error_embed("Permission denied", "Only administrators can use this panel."),
                ephemeral=True
            )
            return

        await interaction.response.send_modal(AddTeamModal())

    @discord.ui.button(label="Add New Manager", style=discord.ButtonStyle.blurple)
    async def add_new_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=error_embed("Permission denied", "Only administrators can use this panel."),
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=info_embed("Choose a team", "Select the team that will receive a new manager."),
            view=TeamSelectForManagerView(),
            ephemeral=True
        )


# -----------------------------
# Contract / Release Views
# -----------------------------
class ContractView(discord.ui.View):
    def __init__(self, contratado_id: int, club_id: str, manager_id: int):
        super().__init__(timeout=None)
        self.contratado_id = contratado_id
        self.club_id = club_id
        self.manager_id = manager_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.contratado_id:
            await interaction.response.send_message(
                embed=error_embed("Not your contract", "This contract was not sent to you."),
                ephemeral=True
            )
            return

        club = get_club_by_id(self.club_id)
        if club is None:
            await interaction.response.send_message(
                embed=error_embed("Team not found", "This team no longer exists."),
                ephemeral=True
            )
            return

        add_player_to_club(interaction.user.id, self.club_id)

        channel = bot.get_channel(CANAL_ACCEPT_ID)
        if channel:
            await channel.send(
                embed=success_embed(
                    "Contract accepted",
                    f"{interaction.user.mention} has joined **{club['name']}**."
                )
            )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=success_embed("Contract accepted", f"You are now a player for **{club['name']}**."),
            view=self
        )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.contratado_id:
            await interaction.response.send_message(
                embed=error_embed("Not your contract", "This contract was not sent to you."),
                ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=warning_embed("Contract declined", "You declined this contract offer."),
            view=self
        )


class SelfReleaseConfirmView(discord.ui.View):
    def __init__(self, user_id: int, club_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.club_id = club_id

    @discord.ui.button(label="Confirm Release", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Not your confirmation", "This confirmation is not for you."),
                ephemeral=True
            )
            return

        club = get_club_by_id(self.club_id)
        if club is None:
            await interaction.response.send_message(
                embed=error_embed("Team not found", "This team no longer exists."),
                ephemeral=True
            )
            return

        removed = remove_player_from_club(interaction.user.id, self.club_id)
        if not removed:
            await interaction.response.send_message(
                embed=warning_embed("Not in team", f"You are not listed in **{club['name']}**."),
                ephemeral=True
            )
            return

        channel = bot.get_channel(CANAL_RELEASE_ID)
        if channel:
            await channel.send(
                embed=warning_embed(
                    "Player released",
                    f"{interaction.user.mention} has left **{club['name']}**."
                )
            )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=success_embed("Released", f"You left **{club['name']}**."),
            view=self
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Not your confirmation", "This confirmation is not for you."),
                ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=warning_embed("Cancelled", "Release cancelled."),
            view=self
        )


# -----------------------------
# Slash Commands
# -----------------------------
@bot.tree.command(name="painel", description="Open the admin team management panel")
async def painel(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message(
            embed=error_embed("Permission denied", "Only administrators can use this command."),
            ephemeral=True
        )
        return

    embed = info_embed(
        "Team Management Panel",
        "Use the buttons below to create teams and assign managers."
    )
    embed.add_field(name="Add New Team", value="Create a new club/team.", inline=False)
    embed.add_field(name="Add New Manager", value="Choose a team and assign a Discord user as manager.", inline=False)

    await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)


@bot.tree.command(name="contract", description="Send a contract offer to a player")
@app_commands.describe(user="Player who will receive the contract")
async def contract(interaction: discord.Interaction, user: discord.Member):
    manager_clubs = get_user_clubs(interaction.user.id)

    if not manager_clubs:
        await interaction.response.send_message(
            embed=error_embed("Permission denied", "You are not registered as a manager for any team."),
            ephemeral=True
        )
        return

    if len(manager_clubs) > 1:
        team_list = "\n".join(f"- {club['name']}" for _, club in manager_clubs)
        await interaction.response.send_message(
            embed=warning_embed(
                "Multiple teams found",
                f"You manage more than one team. Ask an admin to keep only one active team for you.\n\n{team_list}"
            ),
            ephemeral=True
        )
        return

    club_id, club = manager_clubs[0]

    if str(user.id) in club.get("players", []):
        await interaction.response.send_message(
            embed=warning_embed("Already signed", f"{user.mention} is already listed in **{club['name']}**."),
            ephemeral=True
        )
        return

    embed = info_embed(
        "Contract Offer",
        f"You have received a contract offer from **{club['name']}**."
    )
    embed.add_field(name="Manager", value=interaction.user.mention, inline=False)
    embed.add_field(name="Team", value=club["name"], inline=False)

    try:
        await user.send(embed=embed, view=ContractView(user.id, club_id, interaction.user.id))
        await interaction.response.send_message(
            embed=success_embed("Contract sent", f"The contract was sent to {user.mention}'s DM."),
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            embed=error_embed(
                "DM failed",
                "I could not send a DM to this user. They may have direct messages disabled."
            ),
            ephemeral=True
        )


@bot.tree.command(name="release", description="Leave your current team")
async def release(interaction: discord.Interaction):
    club_id, club = get_player_club(interaction.user.id)

    if club is None:
        await interaction.response.send_message(
            embed=warning_embed("No team found", "You are not listed in any team."),
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=warning_embed("Confirm release", f"Do you want to leave **{club['name']}**?"),
        view=SelfReleaseConfirmView(interaction.user.id, club_id),
        ephemeral=True
    )


@bot.tree.command(name="releplayer", description="Release a player from your team")
@app_commands.describe(user="Player to remove from your team")
async def releplayer(interaction: discord.Interaction, user: discord.Member):
    manager_clubs = get_user_clubs(interaction.user.id)

    if not manager_clubs:
        await interaction.response.send_message(
            embed=error_embed("Permission denied", "You are not registered as a manager for any team."),
            ephemeral=True
        )
        return

    if len(manager_clubs) > 1:
        await interaction.response.send_message(
            embed=warning_embed("Multiple teams found", "You manage more than one team. Keep only one active team per manager."),
            ephemeral=True
        )
        return

    club_id, club = manager_clubs[0]

    if str(user.id) not in club.get("players", []):
        await interaction.response.send_message(
            embed=warning_embed("Player not found", f"{user.mention} is not listed in **{club['name']}**."),
            ephemeral=True
        )
        return

    remove_player_from_club(user.id, club_id)

    channel = bot.get_channel(CANAL_RELEASE_ID)
    if channel:
        await channel.send(
            embed=warning_embed(
                "Player released",
                f"{user.mention} was released from **{club['name']}** by {interaction.user.mention}."
            )
        )

    await interaction.response.send_message(
        embed=success_embed("Player released", f"{user.mention} was removed from **{club['name']}**."),
        ephemeral=True
    )


@bot.tree.command(name="squad", description="Show the players from a team")
@app_commands.describe(club="Team name")
@app_commands.autocomplete(club=club_autocomplete)
async def squad(interaction: discord.Interaction, club: str):
    selected_club = get_club_by_id(club)

    if selected_club is None:
        _, selected_club = find_club_by_name(club)

    if selected_club is None:
        await interaction.response.send_message(
            embed=error_embed("Team not found", "No team was found with that name."),
            ephemeral=True
        )
        return

    players = selected_club.get("players", [])

    if not players:
        description = "No players listed yet."
    else:
        description = "\n".join(
            user_display_without_mention(interaction.guild, user_id)
            for user_id in players
        )

    embed = discord.Embed(
        title=f"Squadsheet of club #{selected_club['name']}",
        description=description,
        color=discord.Color.purple()
    )
    embed.set_footer(text="UFA Team System")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="freeagency", description="Post a free agency message")
@app_commands.describe(
    message="Your free agency message",
    position="Your position"
)
async def freeagency(interaction: discord.Interaction, message: str, position: str):
    channel = bot.get_channel(CANAL_FREEAGENCY_ID)

    if channel is None:
        await interaction.response.send_message(
            embed=error_embed("Channel not found", "I could not find the Free Agency channel."),
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="New Free Agency",
        description="A player is looking for a team.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Player", value=interaction.user.mention, inline=False)
    embed.add_field(name="Position", value=position, inline=True)
    embed.add_field(name="Message", value=message, inline=False)
    embed.set_footer(text="UFA Team System")

    await channel.send(content=interaction.user.mention, embed=embed)

    await interaction.response.send_message(
        embed=success_embed("Free agency posted", "Your free agency message was posted successfully."),
        ephemeral=True
    )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online as {bot.user}")


bot.run(TOKEN)
