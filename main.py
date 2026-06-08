@bot.tree.command(name="ban_all", description="⚠️ BAN ALL MEMBERS EXCEPT SPECIFIED USER")
async def ban_all(interaction: discord.Interaction, user_to_keep: discord.User):
    print(f"[DEBUG] /ban_all executado por {interaction.user.name}")
    
    # Confirmação antes de executar
    confirm_embed = discord.Embed(
        title="⚠️ DESTRUCTIVE ACTION ⚠️",
        description=f"Você está prestes a BANIR **TODOS OS MEMBROS** do servidor exceto {user_to_keep.mention}\n\n"
                   f"**Isso irá:**
                   • Banir todos os membros
                   • Remover todos exceto {user_to_keep.name}
                   • **NÃO pode ser desfeito facilmente**
                   
                   Digite **CONFIRMAR** no campo abaixo para prosseguir.",
        color=discord.Color.red()
    )
    
    # Modal de confirmação
    class ConfirmModal(discord.ui.Modal, title="CONFIRM BAN ALL"):
        confirm_text = discord.ui.TextInput(
            label="Digite CONFIRMAR para prosseguir",
            placeholder="CONFIRMAR",
            required=True,
            max_length=10
        )
        
        async def on_submit(self, modal_interaction: discord.Interaction):
            if self.confirm_text.value.upper() != "CONFIRMAR":
                await modal_interaction.response.send_message("❌ Cancelado - Texto incorreto.", ephemeral=True)
                return
            
            await modal_interaction.response.defer(ephemeral=True)
            
            guild = modal_interaction.guild
            bot_member = guild.me
            
            # Verificar permissões do bot
            if not bot_member.guild_permissions.ban_members:
                await modal_interaction.followup.send("❌ Bot não tem permissão de banir membros!", ephemeral=True)
                return
            
            # Coletar todos os membros (exceto bots e o usuário protegido)
            members_to_ban = []
            protected_user_id = user_to_keep.id
            
            for member in guild.members:
                # Não banir o usuário protegido
                if member.id == protected_user_id:
                    continue
                # Não banir o próprio bot
                if member.id == bot.user.id:
                    continue
                # Não banir membros com cargo mais alto que o bot
                if member.top_role >= bot_member.top_role:
                    print(f"[DEBUG] Pulando {member.name} - cargo muito alto")
                    continue
                    
                members_to_ban.append(member)
            
            if not members_to_ban:
                await modal_interaction.followup.send("❌ Nenhum membro para banir!", ephemeral=True)
                return
            
            # Enviar progresso
            progress_embed = discord.Embed(
                title="🔨 BANINDO MEMBROS...",
                description=f"Total a banir: **{len(members_to_ban)}** membros\n"
                           f"Protegido: {user_to_keep.mention}\n\n"
                           f"Status: Iniciando...",
                color=discord.Color.orange()
            )
            await modal_interaction.followup.send(embed=progress_embed, ephemeral=True)
            
            banned_count = 0
            failed_count = 0
            failed_members = []
            
            for i, member in enumerate(members_to_ban):
                try:
                    await member.ban(reason=f"Ban all executado por {modal_interaction.user.name} - Protegido: {user_to_keep.name}")
                    banned_count += 1
                    print(f"[DEBUG] Banido: {member.name} ({member.id})")
                    
                    # Atualizar progresso a cada 10 bans
                    if (i + 1) % 10 == 0 or (i + 1) == len(members_to_ban):
                        progress_embed.description = f"Total a banir: **{len(members_to_ban)}** membros\n" \
                                                     f"Protegido: {user_to_keep.mention}\n\n" \
                                                     f"Status: **{banned_count}/{len(members_to_ban)}** banidos\n" \
                                                     f"Falhas: {failed_count}"
                        await modal_interaction.edit_original_response(embed=progress_embed)
                    
                    await asyncio.sleep(0.5)  # Rate limiting
                    
                except discord.Forbidden:
                    failed_count += 1
                    failed_members.append(f"{member.name} (sem permissão)")
                    print(f"[DEBUG] Falha ao banir {member.name}: Forbidden")
                except Exception as e:
                    failed_count += 1
                    failed_members.append(f"{member.name} ({str(e)[:30]})")
                    print(f"[DEBUG] Falha ao banir {member.name}: {e}")
            
            # Resultado final
            result_embed = discord.Embed(
                title="✅ BAN ALL COMPLETED",
                description=f"**Banidos com sucesso:** {banned_count}\n"
                           f"**Falhas:** {failed_count}\n"
                           f"**Protegido:** {user_to_keep.mention}\n"
                           f"**Membros restantes no servidor:** {len([m for m in guild.members if not m.bot])}",
                color=discord.Color.green() if failed_count == 0 else discord.Color.orange()
            )
            
            if failed_members and len(failed_members) <= 10:
                result_embed.add_field(name="❌ Falha ao banir:", value="\n".join(failed_members[:10]), inline=False)
            elif failed_members:
                result_embed.add_field(name="❌ Falha ao banir:", value=f"{len(failed_members)} membros não puderam ser banidos (cargo muito alto)", inline=False)
            
            result_embed.set_footer(text=f"Executado por {modal_interaction.user.name}")
            result_embed.timestamp = datetime.now()
            
            await modal_interaction.edit_original_response(embed=result_embed)
            
            # Tentar enviar log
            log_channel = bot.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="⚠️ BAN ALL EXECUTADO",
                    description=f"**Executado por:** {modal_interaction.user.mention}\n"
                               f"**Protegido:** {user_to_keep.mention}\n"
                               f"**Banidos:** {banned_count}\n"
                               f"**Falhas:** {failed_count}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await log_channel.send(embed=log_embed)
    
    # Enviar modal de confirmação
    await interaction.response.send_modal(ConfirmModal())
