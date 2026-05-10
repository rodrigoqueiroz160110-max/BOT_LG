import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

OWNER_ID = 1291891135710625805
CANAL_VENDAS_ID = 1302504402514350097

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


class AvaliacaoView(discord.ui.View):
    def __init__(self, log_channel_id: int, log_message_id: int):
        super().__init__(timeout=None)
        self.log_channel_id = log_channel_id
        self.log_message_id = log_message_id

    async def avaliar(self, interaction: discord.Interaction, nota: int):
        canal = bot.get_channel(self.log_channel_id)

        if canal:
            try:
                mensagem = await canal.fetch_message(self.log_message_id)

                if mensagem.embeds:
                    embed = mensagem.embeds[0]
                    embed.set_field_at(
                        index=4,
                        name="Avaliação do cliente:",
                        value=f"{nota}/5 ⭐",
                        inline=False
                    )

                    await mensagem.edit(embed=embed)

            except Exception as e:
                print(f"Erro ao atualizar avaliação: {e}")

        await interaction.response.send_message(
            f"Obrigado pela avaliação! Você avaliou com {nota}/5 ⭐",
            ephemeral=True
        )

        for item in self.children:
            item.disabled = True

        try:
            await interaction.message.edit(view=self)
        except:
            pass

    @discord.ui.button(label="1", style=discord.ButtonStyle.red)
    async def nota_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avaliar(interaction, 1)

    @discord.ui.button(label="2", style=discord.ButtonStyle.red)
    async def nota_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avaliar(interaction, 2)

    @discord.ui.button(label="3", style=discord.ButtonStyle.gray)
    async def nota_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avaliar(interaction, 3)

    @discord.ui.button(label="4", style=discord.ButtonStyle.green)
    async def nota_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avaliar(interaction, 4)

    @discord.ui.button(label="5", style=discord.ButtonStyle.green)
    async def nota_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.avaliar(interaction, 5)


class ValorStockModal(discord.ui.Modal, title="Informações da venda"):
    def __init__(self, canal: discord.TextChannel, produto: str):
        super().__init__()
        self.canal = canal
        self.produto = produto

    valor = discord.ui.TextInput(
        label="Por qual valor irá vender?",
        placeholder="Ex: R$10,00",
        required=True
    )

    stock = discord.ui.TextInput(
        label="Qual o stock?",
        placeholder="Ex: 5 unidades",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Novo Produto Registrado!!",
            color=discord.Color.green()
        )
        embed.add_field(name="Produto:", value=self.produto, inline=False)
        embed.add_field(name="Valor:", value=str(self.valor), inline=False)
        embed.add_field(name="Stock:", value=str(self.stock), inline=False)

        view = CarrinhoView(
            produto=self.produto,
            valor=str(self.valor),
            stock=str(self.stock),
            owner_id=OWNER_ID
        )

        await self.canal.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"Venda enviada em {self.canal.mention}!",
            ephemeral=True
        )


class ProdutoSelect(discord.ui.Select):
    def __init__(self, canal: discord.TextChannel):
        self.canal = canal

        options = [
            discord.SelectOption(label="Bot"),
            discord.SelectOption(label="Server Model"),
            discord.SelectOption(label="Pitch"),
            discord.SelectOption(label="Hub"),
            discord.SelectOption(label="Nitro"),
        ]

        super().__init__(
            placeholder="Selecione o produto que deseja vender",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        produto = self.values[0]
        await interaction.response.send_modal(
            ValorStockModal(self.canal, produto)
        )


class ProdutoView(discord.ui.View):
    def __init__(self, canal: discord.TextChannel):
        super().__init__(timeout=300)
        self.add_item(ProdutoSelect(canal))


class CarrinhoView(discord.ui.View):
    def __init__(self, produto: str, valor: str, stock: str, owner_id: int):
        super().__init__(timeout=None)
        self.produto = produto
        self.valor = valor
        self.stock = stock
        self.owner_id = owner_id

    @discord.ui.button(
        label="Colocar no carrinho 🛒",
        style=discord.ButtonStyle.green
    )
    async def colocar_carrinho(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild
        cliente = interaction.user

        canal_existente = discord.utils.get(
            guild.text_channels,
            name=f"carrinho-de-{cliente.name}".lower()
        )

        if canal_existente:
            await interaction.response.send_message(
                f"Você já tem um carrinho aberto: {canal_existente.mention}",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            cliente: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            )
        }

        owner = guild.get_member(self.owner_id)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        await interaction.response.defer(ephemeral=True)

        canal = await guild.create_text_channel(
            name=f"carrinho-de-{cliente.name}",
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="Olá, bem-vindo! Confirme as opções:",
            color=discord.Color.blue()
        )
        embed.add_field(name="Produto:", value=self.produto, inline=False)
        embed.add_field(name="Valor:", value=self.valor, inline=False)

        await canal.send(
            content=cliente.mention,
            embed=embed,
            view=ConfirmarCarrinhoView(
                produto=self.produto,
                valor=self.valor,
                cliente_id=cliente.id,
                owner_id=self.owner_id
            )
        )

        await interaction.followup.send(
            f"Carrinho criado: {canal.mention}",
            ephemeral=True
        )


class ConfirmarCarrinhoView(discord.ui.View):
    def __init__(self, produto: str, valor: str, cliente_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.produto = produto
        self.valor = valor
        self.cliente_id = cliente_id
        self.owner_id = owner_id

    @discord.ui.button(
        label="Confirmar compra",
        style=discord.ButtonStyle.green
    )
    async def confirmar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.cliente_id:
            await interaction.response.send_message(
                "Apenas o cliente deste carrinho pode confirmar.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            await interaction.message.delete()
        except:
            pass

        embed = discord.Embed(
            title="Compra confirmada!",
            description="Aguarde o atendimento do responsável.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Produto:", value=self.produto, inline=False)
        embed.add_field(name="Valor:", value=self.valor, inline=False)

        await interaction.channel.send(
            content=f"<@{self.owner_id}> atendimento solicitado!",
            embed=embed,
            view=AtendimentoView(
                produto=self.produto,
                valor=self.valor,
                cliente_id=self.cliente_id,
                owner_id=self.owner_id
            )
        )


class AtendimentoView(discord.ui.View):
    def __init__(self, produto: str, valor: str, cliente_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.produto = produto
        self.valor = valor
        self.cliente_id = cliente_id
        self.owner_id = owner_id

    @discord.ui.button(
        label="Encerrar atendimento",
        style=discord.ButtonStyle.red
    )
    async def encerrar(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "Canal será encerrado...",
            ephemeral=True
        )
        await interaction.channel.delete()

    @discord.ui.button(
        label="Compra realizada",
        style=discord.ButtonStyle.blurple
    )
    async def compra_realizada(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Apenas o criador pode usar esse botão.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        cliente = guild.get_member(self.cliente_id)
        canal_vendas = bot.get_channel(CANAL_VENDAS_ID)

        if canal_vendas is None:
            await interaction.followup.send(
                "Erro: canal de vendas não encontrado.",
                ephemeral=True
            )
            return

        cliente_texto = cliente.mention if cliente else f"<@{self.cliente_id}>"

        embed_venda = discord.Embed(
            title="Nova venda realizada!",
            color=discord.Color.green()
        )
        embed_venda.add_field(name="Produto:", value=self.produto, inline=False)
        embed_venda.add_field(name="Valor:", value=self.valor, inline=False)
        embed_venda.add_field(name="Cliente:", value=cliente_texto, inline=False)
        embed_venda.add_field(name="Mensagem:", value="Volte sempre!!", inline=False)
        embed_venda.add_field(
            name="Avaliação do cliente:",
            value="Cliente não avaliou :(",
            inline=False
        )

        mensagem_log = await canal_vendas.send(embed=embed_venda)

        if cliente:
            try:
                embed_dm = discord.Embed(
                    title="Avalie o vendedor!",
                    description="Escolha uma nota de 1 a 5 abaixo.",
                    color=discord.Color.blue()
                )
                embed_dm.add_field(name="Produto:", value=self.produto, inline=False)
                embed_dm.add_field(name="Valor:", value=self.valor, inline=False)

                await cliente.send(
                    embed=embed_dm,
                    view=AvaliacaoView(
                        log_channel_id=CANAL_VENDAS_ID,
                        log_message_id=mensagem_log.id
                    )
                )
            except:
                pass

        try:
            await interaction.user.send(
                f"Nova compra feita!!\n\nProduto: {self.produto}\nValor: {self.valor}"
            )
        except:
            pass

        await interaction.followup.send(
            "Compra aprovada, venda enviada no canal e avaliação enviada na DM do cliente.",
            ephemeral=True
        )

        await interaction.channel.delete()


@bot.tree.command(name="enviarvenda", description="Enviar uma venda em um canal")
@app_commands.describe(canal="Canal onde a venda será enviada")
async def enviarvenda(
    interaction: discord.Interaction,
    canal: discord.TextChannel
):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "Apenas o criador pode usar esse comando.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Quais produtos desejas vender senhor?",
        view=ProdutoView(canal),
        ephemeral=True
    )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online como {bot.user}")


bot.run(TOKEN)