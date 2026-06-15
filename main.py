import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from datetime import datetime

# Ativar intents necessários
intents = discord.Intents.default()
intents.message_content = True  # Precisa estar ativado no portal
intents.members = True  # Opcional

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
    # Aceita emojis normais e personalizados
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
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label="Add New Team", style=discord.ButtonStyle.green)
    async def add_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Iniciar processo de criação de time
        active_creations[interaction.user.id] = {'step': 'emoji'}
        
        embed = discord.Embed(
            title="📝 Create New Team - Step 1/6",
            description="Please send the **team emoji** in this chat.\n\n"
                       "Examples:\n"
                       "• Normal emoji: `⚽`\n"
                       "• Custom emoji: `:FRA:`\n"
                       "• Animated emoji: `<a:name:123456789>`\n\n"
                       "⚠️ You have 2 minutes to respond.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Função para verificar mensagens do usuário
        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
        
        try:
            # Aguardar o emoji
            msg = await bot.wait_for('message', timeout=120.0, check=check)
            emoji_content = msg.content.strip()
            
            # Apagar a mensagem do usuário
            await msg.delete()
            
            if not is_valid_emoji(emoji_content):
                error_embed = discord.Embed(
                    title="❌ Invalid Emoji",
                    description="Please use a valid emoji. Use `/panel` to try again.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                del active_creations[interaction.user.id]
                return
            
            active_creations[interaction.user.id]['emoji'] = emoji_content
            active_creations[interaction.user.id]['step'] = 'name'
            
            # Pedir nome do time
            embed2 = discord.Embed(
                title="📝 Create New Team - Step 2/6",
                description="Please send the **team name** in this chat.\n\n"
                           "Example: `Flamengo Esports`\n\n"
                           "⚠️ You have 2 minutes to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed2, ephemeral=True)
            
            # Aguardar o nome
            msg2 = await bot.wait_for('message', timeout=120.0, check=check)
            team_name = msg2.content.strip()
            await msg2.delete()
            
            if not team_name or len(team_name) > 100:
                await interaction.followup.send("❌ Invalid team name! Use `/panel` to try again.", ephemeral=True)
                del active_creations[interaction.user.id]
                return
            
            active_creations[interaction.user.id]['name'] = team_name
            active_creations[interaction.user.id]['step'] = 'manager'
            
            # Pedir manager
            embed3 = discord.Embed(
                title="📝 Create New Team - Step 3/6",
                description="Please **mention the manager** in this chat.\n\n"
                           "Example: `@username`\n\n"
                           "⚠️ You have 2 minutes to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed3, ephemeral=True)
            
            # Aguardar menção do manager
            msg3 = await bot.wait_for('message', timeout=120.0, check=check)
            
            if not msg3.mentions:
                await interaction.followup.send("❌ Please mention a valid user! Use `/panel` to try again.", ephemeral=True)
                await msg3.delete()
                del active_creations[interaction.user.id]
                return
            
            manager_id = msg3.mentions[0].id
            await msg3.delete()
            active_creations[interaction.user.id]['manager_id'] = manager_id
            active_creations[interaction.user.id]['step'] = 'co_manager'
            
            # Perguntar sobre co-manager
            embed4 = discord.Embed(
                title="📝 Create New Team - Step 4/6",
                description="Do you want to add a **Co-Manager**?\n\n"
                           "Reply with:\n"
                           "• `yes` or `y` - to add a co-manager\n"
                           "• `no` or `n` - to skip\n\n"
                           "⚠️ You have 1 minute to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed4, ephemeral=True)
            
            # Aguardar resposta do co-manager
            msg4 = await bot.wait_for('message', timeout=60.0, check=check)
            response = msg4.content.lower().strip()
            await msg4.delete()
            
            if response in ['yes', 'y', 'sim', 's']:
                embed5 = discord.Embed(
                    title="📝 Create New Team - Step 5/6",
                    description="Please **mention the co-manager** in this chat.\n\n"
                               "Example: `@username`\n"
                               "Or send `skip` to skip\n\n"
                               "⚠️ You have 2 minutes to respond.",
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
                    await interaction.followup.send("⚠️ Invalid input, skipping co-manager...", ephemeral=True)
                    await msg5.delete()
            else:
                active_creations[interaction.user.id]['co_manager_id'] = None
            
            active_creations[interaction.user.id]['step'] = 'limit'
            
            # Perguntar limite
            embed6 = discord.Embed(
                title="📝 Create New Team - Step 6/6",
                description="Please send the **team limit** (1-14)\n\n"
                           "Example: `10`\n\n"
                           "⚠️ You have 1 minute to respond.",
                color=discord.Color.blue()
            )
            
            await interaction.followup.send(embed=embed6, ephemeral=True)
            
            # Aguardar limite
            msg6 = await bot.wait_for('message', timeout=60.0, check=check)
            
            try:
                limit = int(msg6.content.strip())
                if limit < 1 or limit > 14:
                    await interaction.followup.send("❌ Limit must be between 1 and 14! Use `/panel` to try again.", ephemeral=True)
                    await msg6.delete()
                    del active_creations[interaction.user.id]
                    return
                
                await msg6.delete()
                
                # Criar o time
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
                
                # Embed de confirmação
                embed_final = discord.Embed(
                    title="✅ Team Created Successfully",
                    description=f"**Team:** {active_creations[interaction.user.id]['emoji']} {active_creations[interaction.user.id]['name']}\n\n"
                               f"**Manager:** <@{active_creations[interaction.user.id]['manager_id']}>\n"
                               f"**Co-Manager:** {f'<@{active_creations[interaction.user.id]["co_manager_id"]}>' if active_creations[interaction.user.id]['co_manager_id'] else 'None'}\n"
                               f"**Player Limit:** {limit}/14",
                    color=discord.Color.green()
                )
                
                await interaction.followup.send(embed=embed_final, ephemeral=True)
                
                # Log
                await send_log(interaction.guild, f"**Team Created**\nTeam: {active_creations[interaction.user.id]['emoji']} {active_creations[interaction.user.id]['name']}\nManager: <@{active_creations[interaction.user.id]['manager_id']}>\nCreated by: {interaction.user.mention}")
                
                # Limpar dados
                del active_creations[interaction.user.id]
                
            except ValueError:
                await interaction.followup.send("❌ Invalid number! Please use `/panel` to try again.", ephemeral=True)
                await msg6.delete()
                del active_creations[interaction.user.id]
                
        except TimeoutError:
            await interaction.followup.send("⏰ Time expired! Please use `/panel` to try again.", ephemeral=True)
            if interaction.user.id in active_creations:
                del active_creations[interaction.user.id]
    
    @discord.ui.button(label="Delete Team", style=discord.ButtonStyle.red)
    async def delete_team(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not data['teams']:
            await interaction.response.send_message("❌ No teams available!", ephemeral=True)
            return
        
        view = DeleteTeamView()
        await interaction.response.send_message("Select team to delete:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Add Player", style=discord.ButtonStyle.blurple)
    async def add_player(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not data['teams']:
            await interaction.response.send_message("❌ No teams available!", ephemeral=True)
            return
        
        view = AddPlayerView()
        await interaction.response.send_message("Select team to add player:", view=view, ephemeral=True)
    
    @discord.ui.button(label="Remove Manager", style=discord.ButtonStyle.gray)
    async def remove_manager(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not data['teams']:
            await interaction.response.send_message("❌ No teams available!", ephemeral=True)
            return
        
        view = RemoveManagerView()
        await interaction.response.send_message("Select team to remove manager:", view=view, ephemeral=True)

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
            options.append(discord.SelectOption(label=team['name'], value=team_id, emoji=team['emoji'][:2] if team['emoji'] else None))
        super().__init__(placeholder="Select a team...", options=options[:25])
    
    async def callback(self, interaction: discord.Interaction):
        team_id = self.values[0]
        
        if self.action == "delete":
            team = data['teams'].pop(team_id)
            save_data(data)
            await interaction.response.send_message(f"✅ Team **{team['name']}** deleted!", ephemeral=True)
            await send_log(interaction.guild, f"**Team Deleted**\nTeam: {team['emoji']} {team['name']}\nDeleted by: {interaction.user.mention}")
        
        elif self.action == "add":
            # Modal para adicionar jogador
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
        await interaction.response.send_message(f"✅ {self.role.title()} removed from **{team['name']}**!", ephemeral=True)
        await send_log(interaction.guild, f"**Manager Removed**\nTeam: {team['emoji']} {team['name']}\nRemoved: {self.role.title()}\nRemoved by: {interaction.user.mention}")

class AddPlayerModal(discord.ui.Modal, title="Add Player to Team"):
    user_mention = discord.ui.TextInput(
        label="User Mention or ID",
        placeholder="Example: @player or 123456789",
        required=True
    )
    
    def __init__(self, team_id):
        super().__init__()
        self.team_id = team_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Extrair ID da menção
            user_input = self.user_mention.value.strip()
            user_id_match = re.search(r'(\d+)', user_input)
            
            if not user_id_match:
                await interaction.response.send_message("❌ Invalid user! Please mention a user or provide ID.", ephemeral=True)
                return
            
            user_id = int(user_id_match.group(1))
            team = data['teams'][self.team_id]
            
            # Verificações
            for t in data['teams'].values():
                if user_id in t['players']:
                    await interaction.response.send_message("❌ This player is already in another team!", ephemeral=True)
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
            await send_log(interaction.guild, f"**Player Added**\nTeam: {team['emoji']} {team['name']}\nPlayer: <@{user_id}>\nAdded by: {interaction.user.mention}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error adding player!", ephemeral=True)

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
    
    embed = discord.Embed(
        title="⭐ Player Upgraded",
        description=f"**Player:** {user.mention}\n**New Tier:** {tier}\n**Value:** {value}",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)

# ============ TEAM SLASH COMMANDS ============

@bot.tree.command(name="teamlist", description="Show all teams")
async def teamlist(interaction: discord.Interaction):
    if not data['teams']:
        await interaction.response.send_message("❌ No teams created!")
        return
    
    embed = discord.Embed(title="🏆 All Teams", color=discord.Color.blue())
    
    for team_id, team in data['teams'].items():
        manager = f"<@{team['manager_id']}>" if team['manager_id'] else "None"
        co_manager = f"<@{team['co_manager_id']}>" if team.get('co_manager_id') else "None"
        
        embed.add_field(
            name=f"{team['emoji']} {team['name']}",
            value=f"**Manager:** {manager}\n**Co-Manager:** {co_manager}\n**Players:** {len(team['players'])}/{team['limit']}",
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
        await interaction.response.send_message("❌ You are not a manager of any team!", ephemeral=True)
        return
    
    # Check if user already in a team
    for team in data['teams'].values():
        if user.id in team['players']:
            await interaction.response.send_message("❌ This player is already in a team!", ephemeral=True)
            return
    
    embed = discord.Embed(
        title="📄 Contract Offer",
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
        await interaction.response.send_message(f"✅ Contract sent to {user.mention}!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot DM this user! Make sure DMs are open.", ephemeral=True)

class ContractView(discord.ui.View):
    def __init__(self, team_id, manager_id, player_id):
        super().__init__(timeout=300)
        self.team_id = team_id
        self.manager_id = manager_id
        self.player_id = player_id
    
    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ This contract is not for you!", ephemeral=True)
            return
        
        team = data['teams'][str(self.team_id)]
        
        if len(team['players']) >= team['limit']:
            await interaction.response.send_message(f"❌ Team is full! Limit: {team['limit']}", ephemeral=True)
            return
        
        if self.player_id in [p for t in data['teams'].values() for p in t['players']]:
            await interaction.response.send_message("❌ You are already in another team!", ephemeral=True)
            return
        
        team['players'].append(self.player_id)
        
        if str(self.player_id) not in data['players']:
            data['players'][str(self.player_id)] = {'tier': 'D', 'value': '0', 'team': None, 'team_id': None}
        
        data['players'][str(self.player_id)]['team'] = team['name']
        data['players'][str(self.player_id)]['team_id'] = self.team_id
        save_data(data)
        
        await interaction.response.send_message(f"✅ You joined **{team['name']}**!")
        
        guild = interaction.client.get_guild(interaction.guild_id)
        await send_log(guild, f"**Contract Accepted**\nTeam: {team['emoji']} {team['name']}\nPlayer: <@{self.player_id}>")
        
        manager = await interaction.client.fetch_user(self.manager_id)
        if manager:
            await manager.send(f"✅ {interaction.user.mention} accepted the contract for **{team['name']}**!")
        
        self.stop()
    
    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player_id:
            await interaction.response.send_message("❌ This contract is not for you!", ephemeral=True)
            return
        
        team = data['teams'][str(self.team_id)]
        await interaction.response.send_message(f"❌ You declined the contract from **{team['name']}**.")
        
        manager = await interaction.client.fetch_user(self.manager_id)
        if manager:
            await manager.send(f"❌ {interaction.user.mention} declined the contract for **{team['name']}**.")
        
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
    
    players_text = "\n".join(players_list) if players_list else "No players yet"
    
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
    await send_log(interaction.guild, f"**Player Kicked**\nTeam: {user_team['emoji']} {user_team['name']}\nPlayer: {user.mention}\nKicked by: {interaction.user.mention}")
    
    try:
        await user.send(f"❌ You were kicked from **{user_team['name']}** by {interaction.user.mention}!")
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
    await send_log(interaction.guild, f"**Player Left**\nTeam: {user_team['emoji']} {user_team['name']}\nPlayer: {interaction.user.mention}")

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
    
    embed = discord.Embed(
        title="🎮 New Agency Player",
        description=f"**Player:** {interaction.user.mention}\n**Message:** {message}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Current Status", value=f"{team_emoji} {team_status}", inline=False)
    embed.add_field(name="Tier", value=player_data['tier'], inline=True)
    embed.add_field(name="Value", value=player_data['value'], inline=True)
    embed.set_footer(text=f"ID: {interaction.user.id}")
    
    agency_channel = interaction.guild.get_channel(AGENCY_CHANNEL_ID)
    if agency_channel:
        await agency_channel.send(embed=embed)
        await interaction.response.send_message("✅ Your agency profile has been posted!", ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="scouting", description="Post a scouting request")
async def scouting(interaction: discord.Interaction, message: str):
    # Check if user is a manager or co-manager
    is_manager = False
    user_team = None
    
    for team_id, team in data['teams'].items():
        if interaction.user.id in [team['manager_id'], team.get('co_manager_id')]:
            is_manager = True
            user_team = team
            break
    
    if not is_manager:
        await interaction.response.send_message("❌ Only managers can use this command!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔍 Scouting",
        description=f"**Position:** {message}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Team", value=f"{user_team['emoji']} {user_team['name']}", inline=True)
    embed.add_field(name="Manager", value=interaction.user.mention, inline=True)
    embed.set_footer(text="Contact the manager above for trials")
    
    scouting_channel = interaction.guild.get_channel(SCOUTING_CHANNEL_ID)
    if scouting_channel:
        await scouting_channel.send(embed=embed)
        await interaction.response.send_message("✅ Scouting request posted!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Scouting channel not found!", ephemeral=True)

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
