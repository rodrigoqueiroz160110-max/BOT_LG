import os
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

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


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

        for servidor in bot.guilds:
            cargo = servidor.get_role(self.role_id)
            membro = servidor.get_member(self.contratado_id)

            if cargo and membro:
                guild = servidor
                role = cargo
                break

        if guild is None or role is None:
            await interaction.response.send_message(
                "Não consegui encontrar o servidor ou o cargo.",
                ephemeral=True
            )
            return

        membro = guild.get_member(self.contratado_id)

        if membro is None:
            await interaction.response.send_message(
                "Não consegui encontrar você no servidor.",
                ephemeral=True
            )
            return

        try:
            await membro.add_roles(role, reason="Contrato aceito")
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


@bot.tree.command(name="release", description="Sair de um time")
@app_commands.describe(team="Nome do time")
async def release(
    interaction: discord.Interaction,
    team: str
):
    canal = bot.get_channel(CANAL_RELEASE_ID)

    if canal is None:
        await interaction.response.send_message(
            "Canal de release não encontrado.",
            ephemeral=True
        )
        return

    await canal.send(
        f"{interaction.user.mention} saiu do time **{team}**."
    )

    await interaction.response.send_message(
        "Release enviado com sucesso.",
        ephemeral=True
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


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online como {bot.user}")


bot.run(TOKEN)
