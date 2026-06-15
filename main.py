import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from datetime import datetime

# Desabilitar intents privilegiados para evitar erro
intents = discord.Intents.default()
intents.message_content = False
intents.members = False

bot = commands.Bot(command_prefix='/', intents=intents)

# Carregar dados
def load_data():
    if not os.path.exists('data.json'):
        return {'teams': {}, 'players': {}}
    with open('data.json', 'r') as f:
        return json.load(f)

def save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()

# Channel IDs
LOG_CHANNEL_ID = 1515097436329345157
AGENCY_CHANNEL_ID = 1515097317370494996

def is_valid_emoji(emoji_str):
    emoji_pattern = re.compile(r'<:\w+:\d+>|[\U0001F300-\U0001F9FF]')
    return bool(emoji_pattern.match(emoji_str)) or len(emoji_str) <= 2

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f'Error syncing: {e}')

# ============ LOG FUNCTION ============
async def send_log(guild, message):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            description=message,
            color=discord.Color.gray(),
            timestamp=datetime.now()
        )
        await channel.send(embed=embed)

# ============ ADMIN SLASH COMMANDS ============

@bot.tree.command(name="panel", description="Open admin panel")
@app_commands.default_permissions(administrator=True)
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Admin Control Panel",
        description="Manage teams and players",
        color=discord.Color.blue()
    )
    
    view = AdminPanelView()
    await interaction.response.send_message(embed=embed, view=view)

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Add New Team", style=discord.ButtonStyle.green)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CreateTeamModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Delete Team", style=discord.ButtonStyle.red)
    async def delete_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not data['teams']:
            await interaction.response.send_message("No teams available!", ephemeral=True)
            return
        view = DeleteTeamView()
        await interaction.response.send_message("Select team to delete:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Add Player", style=discord.ButtonStyle.blurple)
    async def add_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not data['teams']:
            await interaction.response.send_message("No teams available!", ephemeral=True)
            return
        view = AddPlayerView()
        await interaction.response.send_message("Select team to add player:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Remove Manager", style=discord.ButtonStyle.gray)
    async def remove_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not data['teams']:
            await interaction.response.send_message("No teams available!", ephemeral=True)
            return
        view = RemoveManagerView()
        await interaction.response.send_message("Select team to remove manager:", view=view, ephemeral=True)

class CreateTeamModal(discord.ui.Modal, title="Create New Team"):
    emoji = discord.ui.TextInput(label="Team Emoji", placeholder="Example: ⚽ or <:FLA:123456789>", required=True)
    name = discord.ui.TextInput(label="Team Name", placeholder="Enter team name", required=True)
    manager = discord.ui.TextInput(label="Manager ID", placeholder="Discord ID of manager", required=True)
    co_manager = discord.ui.TextInput(label="Co-Manager ID", placeholder="Discord ID of co-manager", required=False)
    limit = discord.ui.TextInput(label="Team Limit", placeholder="Max players (1-14)", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit.value)
            if limit < 1 or limit > 14:
                await interaction.response.send_message("Limit must be between 1 and 14!", ephemeral=True)
                return
            
            if not is_valid_emoji(self.emoji.value):
                await interaction.response.send_message("Invalid emoji!", ephemeral=True)
                return
            
            manager_id = int(self.manager.value)
            co_manager_id = int(self.co_manager.value) if self.co_manager.value else None
            
            team_id = len(data['teams']) + 1
            
            data['teams'][str(team_id)] = {
                'id': team_id,
                'emoji': self.emoji.value,
                'name': self.name.value,
                'manager_id': manager_id,
                'co_manager_id': co_manager_id,
                'limit': limit,
                'players': [],
                'created_at': datetime.now().isoformat()
            }
            
            save_data(data)
            
            embed = discord.Embed(
                title="Team Created",
                description=f"**Team:** {self.emoji.value} {self.name.value}\n"
                           f"**Manager:** <@{manager_id}>\n"
                           f"**Co-Manager:** {f'<@{co_manager_id}>' if co_manager_id else 'None'}\n"
                           f"**Limit:** {limit}/14",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            
        except ValueError:
            await interaction.response.send_message("Invalid ID or number!", ephemeral=True)

class DeleteTeamView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        select = TeamSelectMenu("delete")
        self.add_item(select)

class AddPlayerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        select = TeamSelectMenu("add")
        self.add_item(select)

class RemoveManagerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        select = TeamSelectMenu("remove")
        self.add_item(select)

class TeamSelectMenu(discord.ui.Select):
    def __init__(self, action):
        self.action = action
        options = []
        for team_id, team in data['teams'].items():
            options.append(discord.SelectOption(label=team['name'], value=team_id))
        super().__init__(placeholder="Select a team...", options=options[:25])
    
    async def callback(self, interaction: discord.Interaction):
        team_id = self.values[0]
        
        if self.action == "delete":
            team = data['teams'].pop(team_id)
            save_data(data)
            await interaction.response.send_message(f"Team **{team['name']}** deleted!", ephemeral=True)
        
        elif self.action == "add":
            modal = AddPlayerModal(team_id)
            await interaction.response.send_modal(modal)
        
        elif self.action == "remove":
            team = data['teams'][team_id]
            view = discord.ui.View(timeout=60)
            
            if team.get('manager_id'):
                view.add_item(RemoveManagerButton(team_id, "manager", team['manager_id']))
            if team.get('co_manager_id'):
                view.add_item(RemoveManagerButton(team_id, "co_manager", team['co_manager_id']))
            
            if len(view.children) == 0:
                await interaction.response.send_message("No managers to remove!", ephemeral=True)
            else:
                await interaction.response.send_message(f"Select manager to remove from **{team['name']}**:", view=view, ephemeral=True)

class RemoveManagerButton(discord.ui.Button):
    def __init__(self, team_id, role, user_id):
        super().__init__(label=f"Remove {role.replace('_', ' ').title()}", style=discord.ButtonStyle.red)
        self.team_id = team_id
        self.role = role
        self.user_id = user_id
    
    async def callback(self, interaction: discord.Interaction):
        team = data['teams'][self.team_id]
        if self.role == "manager":
            team['manager_id'] = None
        else:
            team['co_manager_id'] = None
        save_data(data)
        await interaction.response.send_message(f"{self.role.title()} removed from **{team['name']}**!", ephemeral=True)

class AddPlayerModal(discord.ui.Modal, title="Add Player to Team"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="Discord ID of player", required=True)
    
    def __init__(self, team_id):
        super().__init__()
        self.team_id = team_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id.value)
            team = data['teams'][self.team_id]
            
            if user_id in team['players']:
                await interaction.response.send_message("Player already in this team!", ephemeral=True)
                return
            
            if len(team['players']) >= team['limit']:
                await interaction.response.send_message(f"Team is full! Limit: {team['limit']}", ephemeral=True)
                return
            
            team['players'].append(user_id)
            
            if str(user_id) not in data['players']:
                data['players'][str(user_id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
            
            data['players'][str(user_id)]['team'] = team['name']
            data['players'][str(user_id)]['team_id'] = self.team_id
            save_data(data)
            
            await interaction.response.send_message(f"Added <@{user_id}> to **{team['name']}**!", ephemeral=True)
            await send_log(interaction.guild, f"**Player Added**\nTeam: {team['emoji']} {team['name']}\nPlayer: <@{user_id}>\nAdded by: {interaction.user.mention}")
            
        except ValueError:
            await interaction.response.send_message("Invalid Discord ID!", ephemeral=True)

@bot.tree.command(name="up", description="Upgrade player tier")
@app_commands.default_permissions(administrator=True)
async def upgrade(interaction: discord.Interaction, user: discord.User, tier: str, value: str):
    tier = tier.upper()
    valid_tiers = ['S', 'A', 'B', 'C', 'D']
    
    if tier not in valid_tiers:
        await interaction.response.send_message(f"Invalid tier! Use: {', '.join(valid_tiers)}", ephemeral=True)
        return
    
    if str(user.id) not in data['players']:
        data['players'][str(user.id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
    
    data['players'][str(user.id)]['tier'] = tier
    data['players'][str(user.id)]['value'] = value
    save_data(data)
    
    embed = discord.Embed(
        title="Player Upgraded",
        description=f"**Player:** {user.mention}\n**New Tier:** {tier}\n**Value:** {value}",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)

# ============ TEAM SLASH COMMANDS ============

@bot.tree.command(name="teamlist", description="Show all teams")
async def teamlist(interaction: discord.Interaction):
    if not data['teams']:
        await interaction.response.send_message("No teams created!")
        return
    
    embed = discord.Embed(title="All Teams", color=discord.Color.blue())
    
    for team_id, team in data['teams'].items():
        manager = f"<@{team['manager_id']}>" if team['manager_id'] else "None"
        co_manager = f"<@{team['co_manager_id']}>" if team.get('co_manager_id') else "None"
        
        embed.add_field(
            name=f"{team['emoji']} {team['name']}",
            value=f"Manager: {manager}\nCo-Manager: {co_manager}\nPlayers: {len(team['players'])}/{team['limit']}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="contract", description="Send contract to a player")
async def contract(interaction: discord.Interaction, user: discord.User):
    user_team = None
    user_role = None
    
    for team_id, team in data['teams'].items():
        if team['manager_id'] == interaction.user.id:
            user_team = team
            user_role = "Manager"
            break
        elif team.get('co_manager_id') == interaction.user.id:
            user_team = team
            user_role = "Co-Manager"
            break
    
    if not user_team:
        await interaction.response.send_message("You are not a manager of any team!", ephemeral=True)
        return
    
    for team in data['teams'].values():
        if user.id in team['players']:
            await interaction.response.send_message("This player is already in a team!", ephemeral=True)
            return
    
    embed = discord.Embed(
        title="Contract Offer",
        description=f"You received a contract from **{user_team['name']}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Team", value=f"{user_team['emoji']} {user_team['name']}", inline=True)
    embed.add_field(name="Manager", value=interaction.user.mention, inline=True)
    embed.add_field(name="Role", value=user_role, inline=True)
    embed.set_footer(text="You have 5 minutes to respond")
    
    view = ContractView(user_team['id'], interaction.user.id, user.id)
    
    try:
        await user.send(embed=embed, view=view)
        await interaction.response.send_message(f"Contract sent to {user.mention}!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Cannot DM this user!", ephemeral=True)

class ContractView(discord.ui.View):
    def __init__(self, team_id, manager_id, player_id):
        super().__init__(timeout=300)
        self.team_id = team_id
        self.manager_id = manager_id
        self.player_id = player_id
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("Not for you!", ephemeral=True)
            return
        
        team = data['teams'][str(self.team_id)]
        
        if len(team['players']) >= team['limit']:
            await interaction.response.send_message(f"Team is full!", ephemeral=True)
            return
        
        if self.player_id in [p for t in data['teams'].values() for p in t['players']]:
            await interaction.response.send_message("You are already in another team!", ephemeral=True)
            return
        
        team['players'].append(self.player_id)
        
        if str(self.player_id) not in data['players']:
            data['players'][str(self.player_id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
        
        data['players'][str(self.player_id)]['team'] = team['name']
        data['players'][str(self.player_id)]['team_id'] = self.team_id
        save_data(data)
        
        await interaction.response.send_message(f"You joined **{team['name']}**!")
        
        guild = interaction.client.get_guild(interaction.guild_id)
        await send_log(guild, f"**Contract Accepted**\nTeam: {team['emoji']} {team['name']}\nPlayer: <@{self.player_id}>")
        
        manager = await interaction.client.fetch_user(self.manager_id)
        if manager:
            await manager.send(f"{interaction.user.mention} accepted the contract!")
        
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("Not for you!", ephemeral=True)
            return
        
        team = data['teams'][str(self.team_id)]
        await interaction.response.send_message(f"You declined the contract from **{team['name']}**.")
        
        manager = await interaction.client.fetch_user(self.manager_id)
        if manager:
            await manager.send(f"{interaction.user.mention} declined the contract.")
        
        self.stop()

@bot.tree.command(name="roster", description="Show your team roster")
async def roster(interaction: discord.Interaction):
    user_team = None
    for team_id, team in data['teams'].items():
        if interaction.user.id in [team['manager_id'], team.get('co_manager_id')] or interaction.user.id in team['players']:
            user_team = team
            break
    
    if not user_team:
        await interaction.response.send_message("You are not in any team!")
        return
    
    manager = f"<@{user_team['manager_id']}>" if user_team['manager_id'] else "None"
    co_manager = f"<@{user_team['co_manager_id']}>" if user_team.get('co_manager_id') else "None"
    
    players_list = []
    for player_id in user_team['players']:
        user = await bot.fetch_user(player_id)
        players_list.append(f"@{user.name} | {user.display_name}")
    
    players_text = "\n".join(players_list) if players_list else "No players"
    
    embed = discord.Embed(title=f"Roster of {user_team['name']}", color=discord.Color.blue())
    embed.add_field(name="Manager Team", value=f"Manager: {manager}\nCo-Manager: {co_manager}", inline=False)
    embed.add_field(name=f"Players ({len(user_team['players'])}/{user_team['limit']})", value=players_text, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kick", description="Kick a player from your team")
async def kick(interaction: discord.Interaction, user: discord.User):
    user_team = None
    for team_id, team in data['teams'].items():
        if interaction.user.id in [team['manager_id'], team.get('co_manager_id')]:
            user_team = team
            break
    
    if not user_team:
        await interaction.response.send_message("You are not a manager!", ephemeral=True)
        return
    
    if user.id not in user_team['players']:
        await interaction.response.send_message("Player not in your team!", ephemeral=True)
        return
    
    user_team['players'].remove(user.id)
    
    if str(user.id) in data['players']:
        data['players'][str(user.id)]['team'] = None
        data['players'][str(user.id)]['team_id'] = None
    save_data(data)
    
    await interaction.response.send_message(f"{user.mention} kicked from **{user_team['name']}**!")
    await send_log(interaction.guild, f"**Player Kicked**\nTeam: {user_team['emoji']} {user_team['name']}\nPlayer: {user.mention}\nKicked by: {interaction.user.mention}")
    
    try:
        await user.send(f"You were kicked from **{user_team['name']}**!")
    except:
        pass

@bot.tree.command(name="leaveteam", description="Leave your current team")
async def leaveteam(interaction: discord.Interaction):
    user_team = None
    for team_id, team in data['teams'].items():
        if interaction.user.id in team['players']:
            user_team = team
            break
    
    if not user_team:
        await interaction.response.send_message("You are not in any team!")
        return
    
    user_team['players'].remove(interaction.user.id)
    
    if str(interaction.user.id) in data['players']:
        data['players'][str(interaction.user.id)]['team'] = None
        data['players'][str(interaction.user.id)]['team_id'] = None
    save_data(data)
    
    await interaction.response.send_message(f"You left **{user_team['name']}**!")
    await send_log(interaction.guild, f"**Player Left**\nTeam: {user_team['emoji']} {user_team['name']}\nPlayer: {interaction.user.mention}")

# ============ PLAYER SLASH COMMANDS ============

@bot.tree.command(name="agency", description="Show player agency status")
async def agency(interaction: discord.Interaction):
    player_data = data['players'].get(str(interaction.user.id), {'tier': 'D', 'value': '0', 'team': None})
    
    team_status = "Free Agent"
    team_emoji = "<:FA:1515893495880093877>"
    
    if player_data.get('team'):
        for team_id, team in data['teams'].items():
            if team['name'] == player_data['team']:
                team_status = team['name']
                team_emoji = team['emoji']
                break
    
    embed = discord.Embed(title="New Agency Player", color=discord.Color.blue())
    embed.add_field(name="Current Status", value=f"{team_emoji} {team_status}", inline=False)
    embed.add_field(name="Tier", value=player_data['tier'], inline=True)
    embed.add_field(name="Value", value=player_data['value'], inline=True)
    
    agency_channel = interaction.guild.get_channel(AGENCY_CHANNEL_ID)
    if agency_channel:
        await agency_channel.send(embed=embed)
        await interaction.response.send_message("Agency profile posted!", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="profile", description="Show your player profile")
async def profile(interaction: discord.Interaction):
    player_data = data['players'].get(str(interaction.user.id), {'tier': 'D', 'value': '0', 'team': None})
    
    member = interaction.user
    joined_at = member.joined_at
    days_on_server = (datetime.now() - joined_at.replace(tzinfo=None)).days if joined_at else 0
    
    embed = discord.Embed(title=interaction.user.name, color=discord.Color.blue())
    embed.add_field(name="Tier", value=player_data['tier'], inline=True)
    embed.add_field(name="Value", value=player_data['value'], inline=True)
    embed.add_field(name="Server Time", value=f"{days_on_server} days", inline=True)
    embed.add_field(name="Current Team", value=player_data.get('team', 'Free Agent'), inline=True)
    
    await interaction.response.send_message(embed=embed)

# ============ RUN BOT ============
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("Error: DISCORD_TOKEN not set!")
    exit(1)

bot.run(TOKEN)
