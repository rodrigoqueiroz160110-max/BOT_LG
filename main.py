import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from datetime import datetime

# Ativar intents necessários
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

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
SCOUTING_CHANNEL_ID = 1515901730645082132

# Dicionário para armazenar criação de times ativas
active_creations = {}

def is_valid_emoji(emoji_str):
    emoji_pattern = re.compile(r'<:\w+:\d+>|[\U0001F300-\U0001F9FF]')
    return bool(emoji_pattern.match(emoji_str)) or len(emoji_str) <= 2

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')
    print(f'Intents ativados: Message Content={bot.intents.message_content}')
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f'Error syncing: {e}')

# ============ LOG FUNCTION ============
async def send_log(guild, title, description):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
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
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Add New Team", style=discord.ButtonStyle.green)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        active_creations[interaction.user.id] = {'step': 'emoji'}
        
        embed = discord.Embed(
            title="Create New Team - Step 1/6",
            description="Please send the **team emoji** in this chat.\n\n"
                       "Examples:\n"
                       "• Normal emoji: `⚽`\n"
                       "• Custom emoji: `:FRA:`\n\n"
                       "You have 2 minutes to respond.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
        
        try:
            msg = await bot.wait_for('message', timeout=120.0, check=check)
            emoji_content = msg.content.strip()
            await msg.delete()
            
            if not is_valid_emoji(emoji_content):
                error_embed = discord.Embed(
                    title="Invalid Emoji",
                    description="Please use a valid emoji. Use `/panel` to try again.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                del active_creations[interaction.user.id]
                return
            
            active_creations[interaction.user.id]['emoji'] = emoji_content
            active_creations[interaction.user.id]['step'] = 'name'
            
            embed2 = discord.Embed(
                title="Create New Team - Step 2/6",
                description="Please send the **team name** in this chat.\n\n"
                           "Example: `Flamengo Esports`\n\n"
                           "You have 2 minutes to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed2, ephemeral=True)
            
            msg2 = await bot.wait_for('message', timeout=120.0, check=check)
            team_name = msg2.content.strip()
            await msg2.delete()
            
            if not team_name or len(team_name) > 100:
                await interaction.followup.send("Invalid team name! Use `/panel` to try again.", ephemeral=True)
                del active_creations[interaction.user.id]
                return
            
            active_creations[interaction.user.id]['name'] = team_name
            active_creations[interaction.user.id]['step'] = 'manager'
            
            embed3 = discord.Embed(
                title="Create New Team - Step 3/6",
                description="Please **mention the manager** in this chat.\n\n"
                           "Example: `@username`\n\n"
                           "You have 2 minutes to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed3, ephemeral=True)
            
            msg3 = await bot.wait_for('message', timeout=120.0, check=check)
            
            if not msg3.mentions:
                await interaction.followup.send("Please mention a valid user! Use `/panel` to try again.", ephemeral=True)
                await msg3.delete()
                del active_creations[interaction.user.id]
                return
            
            manager_id = msg3.mentions[0].id
            await msg3.delete()
            active_creations[interaction.user.id]['manager_id'] = manager_id
            active_creations[interaction.user.id]['step'] = 'co_manager'
            
            embed4 = discord.Embed(
                title="Create New Team - Step 4/6",
                description="Do you want to add a **Co-Manager**?\n\n"
                           "Reply with:\n"
                           "• `yes` or `y` - to add a co-manager\n"
                           "• `no` or `n` - to skip\n\n"
                           "You have 1 minute to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed4, ephemeral=True)
            
            msg4 = await bot.wait_for('message', timeout=60.0, check=check)
            response = msg4.content.lower().strip()
            await msg4.delete()
            
            if response in ['yes', 'y', 'sim', 's']:
                embed5 = discord.Embed(
                    title="Create New Team - Step 5/6",
                    description="Please **mention the co-manager** in this chat.\n\n"
                               "Example: `@username`\n"
                               "Or send `skip` to skip\n\n"
                               "You have 2 minutes to respond.",
                    color=discord.Color.blue()
                )
                
                await interaction.followup.send(embed=embed5, ephemeral=True)
                
                msg5 = await bot.wait_for('message', timeout=120.0, check=check)
                
                if msg5.content.lower().strip() == 'skip':
                    active_creations[interaction.user.id]['co_manager_id'] = None
                    await msg5.delete()
                elif msg5.mentions:
                    active_creations[interaction.user.id]['co_manager_id'] = msg5.mentions[0].id
                    await msg5.delete()
                else:
                    active_creations[interaction.user.id]['co_manager_id'] = None
                    await interaction.followup.send("Invalid input, skipping co-manager...", ephemeral=True)
                    await msg5.delete()
            else:
                active_creations[interaction.user.id]['co_manager_id'] = None
            
            active_creations[interaction.user.id]['step'] = 'limit'
            
            embed6 = discord.Embed(
                title="Create New Team - Step 6/6",
                description="Please send the **team limit** (1-14)\n\n"
                           "Example: `10`\n\n"
                           "You have 1 minute to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed6, ephemeral=True)
            
            msg6 = await bot.wait_for('message', timeout=60.0, check=check)
            
            try:
                limit = int(msg6.content.strip())
                if limit < 1 or limit > 14:
                    await interaction.followup.send("Limit must be between 1 and 14! Use `/panel` to try again.", ephemeral=True)
                    await msg6.delete()
                    del active_creations[interaction.user.id]
                    return
                
                await msg6.delete()
                
                team_id = len(data['teams']) + 1
                
                data['teams'][str(team_id)] = {
                    'id': team_id,
                    'emoji': active_creations[interaction.user.id]['emoji'],
                    'name': active_creations[interaction.user.id]['name'],
                    'manager_id': active_creations[interaction.user.id]['manager_id'],
                    'co_manager_id': active_creations[interaction.user.id]['co_manager_id'],
                    'limit': limit,
                    'players': [],
                    'created_at': datetime.now().isoformat()
                }
                
                save_data(data)
                
                embed_final = discord.Embed(
                    title="Team Created Successfully",
                    description=f"**Team:** {active_creations[interaction.user.id]['emoji']} {active_creations[interaction.user.id]['name']}\n\n"
                               f"**Manager:** <@{active_creations[interaction.user.id]['manager_id']}>\n"
                               f"**Co-Manager:** {f'<@{active_creations[interaction.user.id]["co_manager_id"]}>' if active_creations[interaction.user.id]['co_manager_id'] else 'None'}\n"
                               f"**Player Limit:** {limit}/14",
                    color=discord.Color.green()
                )
                
                await interaction.followup.send(embed=embed_final, ephemeral=True)
                
                await send_log(interaction.guild, 
                    "Team Created", 
                    f"**Team:** {active_creations[interaction.user.id]['emoji']} {active_creations[interaction.user.id]['name']}\n"
                    f"**Manager:** <@{active_creations[interaction.user.id]['manager_id']}>\n"
                    f"**Created by:** {interaction.user.mention}")
                
                del active_creations[interaction.user.id]
                
            except ValueError:
                await interaction.followup.send("Invalid number! Please use `/panel` to try again.", ephemeral=True)
                await msg6.delete()
                del active_creations[interaction.user.id]
                
        except TimeoutError:
            await interaction.followup.send("Time expired! Please use `/panel` to try again.", ephemeral=True)
            if interaction.user.id in active_creations:
                del active_creations[interaction.user.id]
    
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

class DeleteTeamView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        
        options = []
        for team_id, team in data['teams'].items():
            options.append(discord.SelectOption(label=team['name'], value=team_id))
        
        if options:
            select = discord.ui.Select(placeholder="Select a team to delete...", options=options[:25])
            select.callback = self.delete_team_callback
            self.add_item(select)
        
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)
    
    async def delete_team_callback(self, interaction: discord.Interaction):
        team_id = interaction.data['values'][0]
        team = data['teams'].pop(team_id)
        save_data(data)
        await interaction.response.edit_message(content=f"✅ Team **{team['name']}** deleted!", view=None)
        await send_log(interaction.guild, "Team Deleted", f"**Team:** {team['emoji']} {team['name']}\n**Deleted by:** {interaction.user.mention}")
    
    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Cancelled.", view=None)

class AddPlayerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        
        options = []
        for team_id, team in data['teams'].items():
            options.append(discord.SelectOption(label=team['name'], value=team_id))
        
        if options:
            select = discord.ui.Select(placeholder="Select a team...", options=options[:25])
            select.callback = self.select_callback
            self.add_item(select)
        
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)
    
    async def select_callback(self, interaction: discord.Interaction):
        team_id = interaction.data['values'][0]
        modal = AddPlayerModal(team_id)
        await interaction.response.send_modal(modal)
    
    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Cancelled.", view=None)

class RemoveManagerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        
        options = []
        for team_id, team in data['teams'].items():
            options.append(discord.SelectOption(label=team['name'], value=team_id))
        
        if options:
            select = discord.ui.Select(placeholder="Select a team...", options=options[:25])
            select.callback = self.select_callback
            self.add_item(select)
        
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self.cancel_callback
        self.add_item(cancel)
    
    async def select_callback(self, interaction: discord.Interaction):
        team_id = interaction.data['values'][0]
        team = data['teams'][team_id]
        
        view = discord.ui.View(timeout=60)
        
        if team.get('manager_id'):
            btn = discord.ui.Button(label="Remove Manager", style=discord.ButtonStyle.red)
            async def remove_mgr(i):
                team['manager_id'] = None
                save_data(data)
                await i.response.edit_message(content=f"✅ Manager removed from **{team['name']}**!", view=None)
                await send_log(i.guild, "Manager Removed", f"**Team:** {team['emoji']} {team['name']}\n**Removed by:** {i.user.mention}")
            btn.callback = remove_mgr
            view.add_item(btn)
        
        if team.get('co_manager_id'):
            btn2 = discord.ui.Button(label="Remove Co-Manager", style=discord.ButtonStyle.red)
            async def remove_comgr(i):
                team['co_manager_id'] = None
                save_data(data)
                await i.response.edit_message(content=f"✅ Co-Manager removed from **{team['name']}**!", view=None)
                await send_log(i.guild, "Co-Manager Removed", f"**Team:** {team['emoji']} {team['name']}\n**Removed by:** {i.user.mention}")
            btn2.callback = remove_comgr
            view.add_item(btn2)
        
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = lambda i: i.response.edit_message(content="Cancelled.", view=None)
        view.add_item(cancel)
        
        await interaction.response.edit_message(content=f"Select manager to remove from **{team['name']}**:", view=view)
    
    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Cancelled.", view=None)

class AddPlayerModal(discord.ui.Modal, title="Add Player to Team"):
    user_id = discord.ui.TextInput(label="User ID", placeholder="Enter Discord ID (right-click user > Copy ID)", required=True)
    
    def __init__(self, team_id):
        super().__init__()
        self.team_id = team_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id.value)
            team = data['teams'][self.team_id]
            
            for t in data['teams'].values():
                if user_id in t['players']:
                    await interaction.response.send_message("❌ Player already in another team!", ephemeral=True)
                    return
            
            if len(team['players']) >= team['limit']:
                await interaction.response.send_message(f"❌ Team is full! Limit: {team['limit']}", ephemeral=True)
                return
            
            team['players'].append(user_id)
            
            if str(user_id) not in data['players']:
                data['players'][str(user_id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
            
            data['players'][str(user_id)]['team'] = team['name']
            data['players'][str(user_id)]['team_id'] = self.team_id
            save_data(data)
            
            await interaction.response.send_message(f"✅ Added <@{user_id}> to **{team['name']}**!", ephemeral=True)
            await send_log(interaction.guild, "Player Added", f"**Team:** {team['emoji']} {team['name']}\n**Player:** <@{user_id}>\n**Added by:** {interaction.user.mention}")
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid ID!", ephemeral=True)

@bot.tree.command(name="up", description="Upgrade player tier")
@app_commands.default_permissions(administrator=True)
async def upgrade(interaction: discord.Interaction, user: discord.User, tier: str, value: str):
    tier = tier.upper()
    valid_tiers = ['S', 'A', 'B', 'C', 'D']
    
    if tier not in valid_tiers:
        await interaction.response.send_message(f"❌ Invalid tier! Use: {', '.join(valid_tiers)}", ephemeral=True)
        return
    
    if str(user.id) not in data['players']:
        data['players'][str(user.id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
    
    data['players'][str(user.id)]['tier'] = tier
    data['players'][str(user.id)]['value'] = value
    save_data(data)
    
    embed = discord.Embed(title="⭐ Player Upgraded", description=f"**Player:** {user.mention}\n**New Tier:** {tier}\n**Value:** {value}", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)
    await send_log(interaction.guild, "Player Upgraded", f"**Player:** {user.mention}\n**New Tier:** {tier}\n**Value:** {value}\n**Upgraded by:** {interaction.user.mention}")

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
        embed.add_field(name=f"{team['emoji']} {team['name']}", value=f"**Manager:** {manager}\n**Co-Manager:** {co_manager}\n**Players:** {len(team['players'])}/{team['limit']}", inline=False)
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
        await interaction.response.send_message("❌ You are not a manager!", ephemeral=True)
        return
    
    for team in data['teams'].values():
        if user.id in team['players']:
            await interaction.response.send_message("❌ Player already in a team!", ephemeral=True)
            return
    
    embed = discord.Embed(title="📄 Contract Offer", description=f"You received a contract from **{user_team['name']}**", color=discord.Color.blue())
    embed.add_field(name="Team", value=f"{user_team['emoji']} {user_team['name']}", inline=True)
    embed.add_field(name="Manager", value=interaction.user.mention, inline=True)
    embed.add_field(name="Role", value=user_role, inline=True)
    embed.set_footer(text="You have 5 minutes")
    
    view = ContractView(user_team['id'], interaction.user.id, user.id, interaction.guild_id)
    
    try:
        await user.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Contract sent to {user.mention}!", ephemeral=True)
        await send_log(interaction.guild, "Contract Sent", f"**Team:** {user_team['emoji']} {user_team['name']}\n**To:** {user.mention}\n**Sent by:** {interaction.user.mention}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot DM this user!", ephemeral=True)

class ContractView(discord.ui.View):
    def __init__(self, team_id, manager_id, player_id, guild_id):
        super().__init__(timeout=300)
        self.team_id = team_id
        self.manager_id = manager_id
        self.player_id = player_id
        self.guild_id = guild_id
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ Not for you!", ephemeral=True)
            return
        
        team = data['teams'][str(self.team_id)]
        
        if len(team['players']) >= team['limit']:
            await interaction.response.send_message("❌ Team is full!", ephemeral=True)
            return
        
        if self.player_id in [p for t in data['teams'].values() for p in t['players']]:
            await interaction.response.send_message("❌ You are already in a team!", ephemeral=True)
            return
        
        team['players'].append(self.player_id)
        
        if str(self.player_id) not in data['players']:
            data['players'][str(self.player_id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
        
        data['players'][str(self.player_id)]['team'] = team['name']
        data['players'][str(self.player_id)]['team_id'] = self.team_id
        save_data(data)
        
        await interaction.response.send_message(f"✅ You joined **{team['name']}**!")
        
        guild = interaction.client.get_guild(self.guild_id)
        await send_log(guild, "Contract Accepted", f"**Team:** {team['emoji']} {team['name']}\n**Player:** {interaction.user.mention}\n**Manager:** <@{self.manager_id}>")
        
        manager = await interaction.client.fetch_user(self.manager_id)
        if manager:
            await manager.send(f"✅ {interaction.user.mention} accepted the contract!")
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ Not for you!", ephemeral=True)
            return
        
        team = data['teams'][str(self.team_id)]
        await interaction.response.send_message(f"❌ You declined the contract from **{team['name']}**.")
        
        guild = interaction.client.get_guild(self.guild_id)
        await send_log(guild, "Contract Declined", f"**Team:** {team['emoji']} {team['name']}\n**Player:** {interaction.user.mention}\n**Manager:** <@{self.manager_id}>")
        
        manager = await interaction.client.fetch_user(self.manager_id)
        if manager:
            await manager.send(f"❌ {interaction.user.mention} declined the contract.")
        self.stop()

@bot.tree.command(name="roster", description="Show your team roster")
async def roster(interaction: discord.Interaction):
    user_team = None
    for team_id, team in data['teams'].items():
        if interaction.user.id in [team['manager_id'], team.get('co_manager_id')] or interaction.user.id in team['players']:
            user_team = team
            break
    
    if not user_team:
        await interaction.response.send_message("❌ You are not in any team!")
        return
    
    manager = f"<@{user_team['manager_id']}>" if user_team['manager_id'] else "None"
    co_manager = f"<@{user_team['co_manager_id']}>" if user_team.get('co_manager_id') else "None"
    
    players_list = []
    for player_id in user_team['players']:
        try:
            user = await bot.fetch_user(player_id)
            players_list.append(f"@{user.name} | {user.display_name}")
        except:
            players_list.append(f"User ID: {player_id}")
    
    players_text = "\n".join(players_list) if players_list else "No players"
    
    embed = discord.Embed(title=f"📋 Roster of {user_team['name']}", color=discord.Color.blue())
    embed.add_field(name="Manager Team", value=f"**Manager:** {manager}\n**Co-Manager:** {co_manager}", inline=False)
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
        await interaction.response.send_message("❌ You are not a manager!", ephemeral=True)
        return
    
    if user.id not in user_team['players']:
        await interaction.response.send_message("❌ Player not in your team!", ephemeral=True)
        return
    
    user_team['players'].remove(user.id)
    
    if str(user.id) in data['players']:
        data['players'][str(user.id)]['team'] = None
        data['players'][str(user.id)]['team_id'] = None
    save_data(data)
    
    await interaction.response.send_message(f"✅ {user.mention} kicked from **{user_team['name']}**!")
    await send_log(interaction.guild, "Player Kicked", f"**Team:** {user_team['emoji']} {user_team['name']}\n**Player:** {user.mention}\n**Kicked by:** {interaction.user.mention}")
    
    try:
        await user.send(f"❌ You were kicked from **{user_team['name']}**!")
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
        await interaction.response.send_message("❌ You are not in any team!")
        return
    
    user_team['players'].remove(interaction.user.id)
    
    if str(interaction.user.id) in data['players']:
        data['players'][str(interaction.user.id)]['team'] = None
        data['players'][str(interaction.user.id)]['team_id'] = None
    save_data(data)
    
    await interaction.response.send_message(f"✅ You left **{user_team['name']}**!")
    await send_log(interaction.guild, "Player Left", f"**Team:** {user_team['emoji']} {user_team['name']}\n**Player:** {interaction.user.mention}")

# ============ PLAYER SLASH COMMANDS ============

@bot.tree.command(name="agency", description="Post your agency profile")
async def agency(interaction: discord.Interaction, message: str):
    player_data = data['players'].get(str(interaction.user.id), {'tier': 'D', 'value': '0', 'team': None})
    
    team_status = "Free Agent"
    team_emoji = "<:FA:1515893495880093877>"
    
    if player_data.get('team'):
        for team_id, team in data['teams'].items():
            if team['name'] == player_data['team']:
                team_status = team['name']
                team_emoji = team['emoji']
                break
    
    embed = discord.Embed(title="🎮 New Agency Player", description=f"**Player:** {interaction.user.mention}\n**Message:** {message}", color=discord.Color.blue())
    embed.add_field(name="Current Status", value=f"{team_emoji} {team_status}", inline=False)
    embed.add_field(name="Tier", value=player_data['tier'], inline=True)
    embed.add_field(name="Value", value=player_data['value'], inline=True)
    embed.set_footer(text=f"ID: {interaction.user.id}")
    
    agency_channel = interaction.guild.get_channel(AGENCY_CHANNEL_ID)
    if agency_channel:
        await agency_channel.send(embed=embed)
        await interaction.response.send_message("✅ Agency profile posted!", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="scouting", description="Post a scouting request")
async def scouting(interaction: discord.Interaction, message: str):
    is_manager = False
    user_team = None
    
    for team_id, team in data['teams'].items():
        if interaction.user.id in [team['manager_id'], team.get('co_manager_id')]:
            is_manager = True
            user_team = team
            break
    
    if not is_manager:
        await interaction.response.send_message("❌ Only managers can use this!", ephemeral=True)
        return
    
    embed = discord.Embed(title="🔍 Scouting", description=f"**Position:** {message}", color=discord.Color.blue())
    embed.add_field(name="Team", value=f"{user_team['emoji']} {user_team['name']}", inline=True)
    embed.add_field(name="Manager", value=interaction.user.mention, inline=True)
    embed.set_footer(text="Contact the manager for trials")
    
    scouting_channel = interaction.guild.get_channel(SCOUTING_CHANNEL_ID)
    if scouting_channel:
        await scouting_channel.send(embed=embed)
        await interaction.response.send_message("✅ Scouting request posted!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Channel not found!", ephemeral=True)

@bot.tree.command(name="profile", description="Show your player profile")
async def profile(interaction: discord.Interaction):
    player_data = data['players'].get(str(interaction.user.id), {'tier': 'D', 'value': '0', 'team': None})
    
    member = interaction.user
    joined_at = member.joined_at
    days_on_server = (datetime.now() - joined_at.replace(tzinfo=None)).days if joined_at else 0
    
    embed = discord.Embed(title=f"👤 {interaction.user.name}", color=discord.Color.blue())
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
