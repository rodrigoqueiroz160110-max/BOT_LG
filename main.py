```python
import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

CARGOS_CONTRACT = [
    1503241324277796864,
    1503241325137629315
]

CANAL_ACCEPT_ID = 1503241511696076831
CANAL_RELEASE_ID = 1503241512819888129
CANAL_FREEAGENCY_ID = 1503241510320341134

CONTRACTS_FILE = "contracts.json"

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def carregar_contracts():
    if not os.path.exists(CONTRACTS_FILE):
        return {}

    with open(CONTRACTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_contracts(data):
    with open(CONTRACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def salvar_ultimo_contract(user_id: int, role_id: int):
    data = carregar_contracts()
    data[str(user_id)] = role_id
    salvar_contracts(data)


def pegar_ultimo_contract(user_id: int):
    data = carregar_contracts()
    return data.get(str(user_id))


def remover_ultimo_contract(user_id: int):
    data = carregar_contracts()
    data.pop(str(user_id), None)
    salvar_contracts(data)


def pode_usar_contract(member: discord.Member):
    return any(role.id in CARGOS_CONTRACT for role in member.roles)


class ContractView(discord.ui.View):
    def __init__(self, contratado_id: int, role_id: int):
        super().__init__(timeout=None)
        self.contratado_id = contratado_id
        self.role_id = role_id

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green)
    async def aceitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.contratado_id:
            await interaction.response.send_message(
                "Esse contrato não é para você.",
                ephemeral=True
            )
            return

        guild = None
        role = None
        membro = None

        for servidor in bot.guilds:
            cargo = servidor.get_role(self.role_id)
            membro_servidor = servidor.get_member(self.contratado_id)

            if cargo and membro_servidor:
                guild = servidor
                role = cargo
                membro = membro_servidor
                break

        if guild is None or role is None or membro is None:
            await interaction.response.send_message(
                "Não consegui encontrar o servidor, cargo ou usuário.",
                ephemeral=True
            )
            return

        try:
            await membro.add_roles(role, reason="Contrato aceito")
            salvar_ultimo_contract(membro.id, role.id)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Não consegui dar o cargo. Coloque o cargo do bot acima desse cargo.",
                ephemeral=True
            )
            return

        canal = bot.get_channel(CANAL_ACCEPT_ID)

        if canal:
            embed = discord.Embed(
                title="Contrato aceito!",
                description=f"{membro.mention} aceitou o contrato e entrou no time **{role.name}**.",
                color=discord.Color.green()
            )
            await canal.send(embed=embed)

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Você aceitou o contrato e recebeu o cargo!",
            view=self
        )

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.red)
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.contratado_id:
            await interaction.response.send_message(
                "Esse contrato não é para você.",
                ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Você recusou o contrato.",
            view=self
        )


class ReleaseConfirmView(discord.ui.View):
    def __init__(self, user_id: int, role_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.role_id = role_id

    @discord.ui.button(label="Confirmar saída", style=discord.ButtonStyle.red)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Essa confirmação não é para você.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        membro = interaction.user
        role = guild.get_role(self.role_id)

        if role is None:
            await interaction.response.send_message(
                "Não encontrei o cargo do seu último contract.",
                ephemeral=True
            )
            return

        if role not in membro.roles:
            remover_ultimo_contract(membro.id)
            await interaction.response.send_message(
                "Você não tem mais esse cargo.",
                ephemeral=True
            )
            return

        try:
            await membro.remove_roles(role, reason="Release confirmado")
            remover_ultimo_contract(membro.id)
        except discord.Forbidden:
            await interaction.response.send_message(
                "Não consegui remover o cargo. Meu cargo precisa estar acima dele.",
                ephemeral=True
            )
            return

        canal = bot.get_channel(CANAL_RELEASE_ID)

        if canal:
            await canal.send(
                f"{membro.mention} saiu do time **{role.name}**."
            )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=f"Você saiu do time **{role.name}**.",
            view=self
        )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.gray)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Essa confirmação não é para você.",
                ephemeral=True
            )
            return

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Saída cancelada.",
            view=self
        )


@bot.tree.command(name="contract", description="Enviar contrato para um usuário")
@app_commands.describe(
    user="Usuário que será contratado",
    team="Cargo/time que o usuário vai receber"
)
async def contract(
    interaction: discord.Interaction,
    user: discord.Member,
    team: discord.Role
):
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "Erro ao verificar seus cargos.",
            ephemeral=True
        )
        return

    if not pode_usar_contract(interaction.user):
        await interaction.response.send_message(
            "Você não tem permissão para usar esse comando.",
            ephemeral=True
        )
        return

    if team.permissions.administrator:
        await interaction.response.send_message(
            "Você não pode usar um cargo com permissão de administrador.",
            ephemeral=True
        )
        return

    if team >= interaction.user.top_role:
        await interaction.response.send_message(
            "Você só pode contratar para cargos abaixo do seu maior cargo.",
            ephemeral=True
        )
        return

    bot_member = interaction.guild.me

    if team >= bot_member.top_role:
        await interaction.response.send_message(
            "Eu não consigo dar esse cargo. Meu cargo precisa estar acima dele.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Você recebeu um contrato!",
        description=f"Você foi contratado para o time **{team.name}**.",
        color=discord.Color.blue()
    )

    embed.add_field(name="Contratante:", value=interaction.user.mention, inline=False)
    embed.add_field(name="Time:", value=team.mention, inline=False)

    try:
        await user.send(
            embed=embed,
            view=ContractView(user.id, team.id)
        )

        await interaction.response.send_message(
            f"Contrato enviado na DM de {user.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "Não consegui mandar DM para esse usuário. Talvez ele esteja com a DM fechada.",
            ephemeral=True
        )


@bot.tree.command(name="release", description="Sair do último time recebido por contract")
async def release(interaction: discord.Interaction):
    role_id = pegar_ultimo_contract(interaction.user.id)

    if role_id is None:
        await interaction.response.send_message(
            "Você não tem nenhum contract salvo para sair.",
            ephemeral=True
        )
        return

    role = interaction.guild.get_role(role_id)

    if role is None:
        remover_ultimo_contract(interaction.user.id)
        await interaction.response.send_message(
            "O cargo do seu último contract não existe mais.",
            ephemeral=True
        )
        return

    if role not in interaction.user.roles:
        remover_ultimo_contract(interaction.user.id)
        await interaction.response.send_message(
            "Você não tem mais o cargo do seu último contract.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Confirmar release",
        description=f"Você tem certeza que quer sair do time **{role.name}**?",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        view=ReleaseConfirmView(interaction.user.id, role.id)
    )


@bot.tree.command(name="squad", description="Mostrar membros de um cargo/time")
@app_commands.describe(team="Cargo do time")
async def squad(
    interaction: discord.Interaction,
    team: discord.Role
):
    if team.permissions.administrator:
        await interaction.response.send_message(
            "Você não pode selecionar um cargo com permissão de administrador.",
            ephemeral=True
        )
        return

    membros = team.members

    if not membros:
        lista = "Nenhum usuário encontrado nesse cargo."
    else:
        lista = "\n".join(
            [f"P: {membro.mention} Class D" for membro in membros]
        )

    embed = discord.Embed(
        title=f"SquadSheet of {team.name}",
        description=lista,
        color=discord.Color.purple()
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="freeagency", description="Enviar uma mensagem de Free Agency")
@app_commands.describe(
    message="Mensagem da sua free agency",
    position="Sua posição"
)
async def freeagency(
    interaction: discord.Interaction,
    message: str,
    position: str
):
    canal = bot.get_channel(CANAL_FREEAGENCY_ID)

    if canal is None:
        await interaction.response.send_message(
            "Não consegui encontrar o canal de Free Agency.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="New Free agency!",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="User:",
        value=interaction.user.mention,
        inline=False
    )

    embed.add_field(
        name="Message:",
        value=message,
        inline=False
    )

    embed.add_field(
        name="Position:",
        value=position,
        inline=False
    )

    embed.set_footer(text="Powered by UFA Team")

    await canal.send(
        content=interaction.user.mention,
        embed=embed
    )

    await interaction.response.send_message(
        "Free agency enviada com sucesso.",
        ephemeral=True
    )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online como {bot.user}")


bot.run(TOKEN)
```
