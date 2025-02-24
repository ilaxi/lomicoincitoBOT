import sys
import types
if "audioop" not in sys.modules:
    audioop = types.ModuleType("audioop")
    def dummy_lin2lin(data, width, width2):
        return data
    def dummy_add(data, data2, width):
        return data
    def dummy_ratecv(data, width, n, r, s, w):
        return data, 0, 0
    audioop.lin2lin = dummy_lin2lin
    audioop.add = dummy_add
    audioop.ratecv = dummy_ratecv
    sys.modules["audioop"] = audioop

import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os, random, time, asyncio, datetime
import webserver

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "data.json"
# ---------------------------
# Carga/guardado de datos
# ---------------------------
data = {}
def load_data():
    global data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
            except json.decoder.JSONDecodeError:
                data = {}
    else:
        data = {}
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
def get_user(user_id):
    if str(user_id) not in data:
        data[str(user_id)] = {
            "lomitos": 0,
            "xp": 0,
            "level": 1,
            "last_pedir": 0,
            "last_sueldo": 0,
            "shop": {
                "lomitero": 0,
                "lomiteria": 0,
                "amulet": 0,
                "hipopotamo": 0,
                "arabe": 0,
                "mezquita": 0
            },
            "inventory": {},
            "donado": 0,
            "recibido": 0
        }
        save_data()
    return data[str(user_id)]
# ---------------------------
# Items y precios
# ---------------------------
ITEMS = {
    "lomitero": {"name": "Lomitero👨🏿‍🍳", "base": 1, "growth": 1.5, "level": 1},
    "lomiteria": {"name": "Lomiteria🏪", "base": 10, "growth": 1.5, "level": 1},
    "amulet": {"name": "🪬's", "base": 100, "growth": 3, "level": 1, "max": 5},
    "hipopotamo": {"name": "hipopotamos 🦛", "base": 1000, "growth": 2, "level": 5},
    "arabe": {"name": "Árabe👳🏽‍♂️", "base": 5000, "growth": 2, "level": 10},
    "mezquita": {"name": "Mezquitas 🕌", "base": 10000, "growth": 2, "level": 15}
}
def get_item_price(item_key, current_count):
    info = ITEMS[item_key]
    exponent = current_count + 1 if item_key == "lomitero" else current_count
    return int(info["base"] * (info["growth"] ** exponent))
# ---------------------------
# Producción y XP
# ---------------------------
def compute_hourly_production(user_data):
    shop = user_data.get("shop", {})
    lomitero_count = shop.get("lomitero", 0)
    lomiteria_count = shop.get("lomiteria", 0)
    # Buffeo de lomiteros
    buff_active = user_data.get("buffeo_until", 0) > time.time()
    lomitero_multiplier = 2 if buff_active else 1
    # Lomiterias temporales
    if user_data.get("extra_lomiteria_until", 0) > time.time():
        lomiteria_count += user_data.get("extra_lomiteria_bonus", 0)
    
    lomiteros_production = lomitero_count * (1 + lomiteria_count) * lomitero_multiplier
    
    hipopotamo_count = shop.get("hipopotamo", 0)
    hipopotamo_production = int((10000 * hipopotamo_count) / 24)
    
    arabe_count = shop.get("arabe", 0)
    mezquita_count = shop.get("mezquita", 0)
    arabe_production = arabe_count * (10 + 10 * mezquita_count)
    
    return lomiteros_production + hipopotamo_production + arabe_production

def compute_xp_gain(user_data):
    hipopotamo_count = user_data.get("shop", {}).get("hipopotamo", 0)
    return 1 + (0.2 * hipopotamo_count)

def check_level_up(user_data):
    current_level = user_data["level"]
    xp_needed = 40 * current_level
    if user_data["xp"] >= xp_needed:
        user_data["xp"] -= xp_needed
        user_data["level"] += 1
        return True
    return False
# ---------------------------
# auto-borrar mensajes
# ---------------------------
async def delete_after(message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass
# ---------------------------
# Bot
# ---------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
@bot.event
async def on_ready():
    load_data()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} comandos de barra.")
    except Exception as e:
        print(e)
    print(f"Bot conectado como {bot.user}.")
    production_task.start()
# producción p/h
@tasks.loop(hours=1)
async def production_task():
    for user_id, user_data in data.items():
        prod = compute_hourly_production(user_data)
        user_data["lomitos"] += prod
    save_data()
    print("Producción horaria aplicada a todos los usuarios.")
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        user_data = get_user(interaction.user.id)
        xp_gain = compute_xp_gain(user_data)
        user_data["xp"] += xp_gain
        leveled_up = False
        while check_level_up(user_data):
            leveled_up = True
        if leveled_up:
            await interaction.channel.send(f"¡Felicidades {interaction.user.mention}, subiste a nivel {user_data['level']}!")
        save_data()
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    user_data = get_user(message.author.id)
    xp_gain = compute_xp_gain(user_data)
    user_data["xp"] += xp_gain
    leveled_up = False
    while check_level_up(user_data):
        leveled_up = True
    if leveled_up:
        await message.channel.send(f"amor {message.author.mention}, subiste a nivel {user_data['level']}!")
    save_data()
    await bot.process_commands(message)
# ---------------------------
# /pedir
# ---------------------------
@bot.tree.command(name="pedir", description="pedí tus 🌯")
async def pedir(interaction: discord.Interaction):
    user_data = get_user(interaction.user.id)
    now = time.time()
    amulet_count = user_data.get("shop", {}).get("amulet", 0)
    effective_cooldown = max(60 - 10 * amulet_count, 10)
    if now - user_data.get("last_pedir", 0) < effective_cooldown:
        remaining = int(effective_cooldown - (now - user_data.get("last_pedir", 0)))
        await interaction.response.send_message(f"Espera {remaining} segundos para volver a pedir.", ephemeral=True)
        return
    reward = 1 + amulet_count
    user_data["lomitos"] += reward
    user_data["last_pedir"] = now
    save_data()
    await interaction.response.send_message(f"recibiste **{reward}🌯** y actualmente tenés **{user_data['lomitos']}🌯**.", ephemeral=False)
    msg = await interaction.original_response()
    asyncio.create_task(delete_after(msg, 30))
# ---------------------------
# /sueldo 
# ---------------------------
@bot.tree.command(name="sueldo", description="cobra tu sueldo cada 24 horas")
async def sueldo(interaction: discord.Interaction):
    user_data = get_user(interaction.user.id)
    now = time.time()
    if now - user_data.get("last_sueldo", 0) < 24 * 3600:
        remaining = int(24 * 3600 - (now - user_data.get("last_sueldo", 0)))
        horas = remaining // 3600
        await interaction.response.send_message(f"tenés q esperar {horas} horas para cobrar de nuevo.", ephemeral=True)
        return
    user_data["last_sueldo"] = now
    if random.random() < 0.7:
        hourly = compute_hourly_production(user_data)
        multiplier = random.uniform(0.8, 2.0)
        amount = int(hourly * multiplier)
        user_data["lomitos"] += amount
        save_data()
        await interaction.response.send_message(f"recibiste **{amount}🌯** de sueldo. Ahora te quedan **{user_data['lomitos']}🌯**.", ephemeral=False)
    else:
        items_probabilities = [
            ("Cliente👦🏼", 0.20),
            ("buffeo de lomiteros🆙", 0.20),
            ("xp extra✅", 0.30),
            ("lomiteria de alquiler🚨", 0.07),
            ("salto temporal⏰", 0.10),
            ("reclutar lomitero👨🏿‍🍳", 0.05),
            ("caramelo raro🍬", 0.05),
            ("lomiteria gratis🏪", 0.024),
            ("lomicoincita🦛", 0.005),
            ("mortero bala🧑🏿‍🦲", 0.001)
        ]
        rand = random.random()
        cumulative = 0
        selected_item = None
        for item, prob in items_probabilities:
            cumulative += prob
            if rand <= cumulative:
                selected_item = item
                break
        if selected_item is None:
            selected_item = "Cliente👦🏼"
        inv = user_data.get("inventory", {})
        inv[selected_item] = inv.get(selected_item, 0) + 1
        user_data["inventory"] = inv
        save_data()
        await interaction.response.send_message(f"ganaste este item: **{selected_item}**", ephemeral=False)
    msg = await interaction.original_response()
    asyncio.create_task(delete_after(msg, 40))
# ---------------------------
# /biggieinfo
# ---------------------------
@bot.tree.command(name="biggieinfo", description="info de items y cosas")
async def biggieinfo(interaction: discord.Interaction):
    desc = (
        "**Lomitero👨🏿‍🍳:** Genera 1🌯 por hora.\n"
        "**Lomiteria🏪:** Cada lomitero genera 1🌯 adicional por cada lomiteria que compres.\n"
        "**🪬's:** Aumenta el /pedir (más 🌯 y reduce 10s del cooldown, máx 5).\n"
        "**Hipopotamos:** Cada uno da 10,000🌯 cada 24h y +20% de ganancia de XP.\n"
        "**Árabe👳🏽‍♂️:** Genera 10🌯 por hora.\n"
        "**Mezquitas 🕌:** Cada Árabe genera 10🌯 adicionales por cada Mezquita.\n\n"
        "Items de suerte en /sueldo:\n"
        "- **Cliente👦🏼:** Genera instantáneamente la producción de todos tus lomiteros.\n"
        "- **buffeo de lomiteros🆙:** tus lomiteros producen el doble de 🌯 por 24h.\n"
        "- **xp extra✅:** Rellena un 15% de tu XP para subir de nivel.\n"
        "- **lomiteria de alquiler🚨:** Ganas 5 lomiterias extra por 24h.\n"
        "- **salto temporal⏰:** Resetea el cooldown de /sueldo.\n"
        "- **reclutar lomitero👨🏿‍🍳:** ganas 1 lomitero gratis.\n"
        "- **caramelo raro🍬:** Subis automáticamente al siguiente nivel.\n"
        "- **lomiteria gratis🏪:** ganas 1 lomiteria gratis.\n"
        "- **lomicoincita🦛:** Recibís 1,000,000🌯.\n"
        "- **mortero bala🧑🏿‍🦲:** Recibís 10,000,000🌯."
    )
    embed = discord.Embed(title="Biggie Info", description=desc, color=0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=False)
    msg = await interaction.original_response()
    asyncio.create_task(delete_after(msg, 40))
# ---------------------------
# /biggieprecios
# ---------------------------
@bot.tree.command(name="biggieprecios", description="precios actuales del biggie")
async def biggieprecios(interaction: discord.Interaction):
    user_data = get_user(interaction.user.id)
    shop = user_data.get("shop", {})
    texto = ""
    for key, info in ITEMS.items():
        owned = shop.get(key, 0)
        price = get_item_price(key, owned)
        texto += f"{info['name']}: **{price}🌯** (tenés: {owned})\n"
    await interaction.response.send_message(texto, ephemeral=False)
    msg = await interaction.original_response()
    asyncio.create_task(delete_after(msg, 30))
# ---------------------------
# Confirmar compra /biggie
# ---------------------------
class ConfirmPurchaseView(discord.ui.View):
    def __init__(self, item_key, price):
        super().__init__(timeout=30)
        self.item_key = item_key
        self.price = price
    @discord.ui.button(label="comprar", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        user_data = get_user(interaction.user.id)
        current_count = user_data["shop"].get(self.item_key, 0)
        if user_data["lomitos"] < self.price:
            await interaction.followup.send("No tenés suficientes🌯.", ephemeral=False)
            try:
                await interaction.message.delete()
            except Exception:
                pass
            return
        user_data["lomitos"] -= self.price
        user_data["shop"][self.item_key] = current_count + 1
        save_data()
        new_price = get_item_price(self.item_key, current_count + 1)
        new_quantity = user_data["shop"][self.item_key]
        final_text = (
            f"Compraste **1** **{ITEMS[self.item_key]['name']}** por **{self.price}**🌯. "
            f"Ahora tenés **{new_quantity}** **{ITEMS[self.item_key]['name']}** "
            f"y el siguiente cuesta **{new_price}**🌯."
        )
        await interaction.followup.send(final_text, ephemeral=False)
        await asyncio.sleep(1)
        try:
            await interaction.message.delete()
        except Exception:
            pass
    @discord.ui.button(label="bueno, no", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.followup.send("Compra cancelada.", ephemeral=False)
        await asyncio.sleep(1)
        try:
            await interaction.message.delete()
        except Exception:
            pass
# ---------------------------
# /biggie 
# ---------------------------
class PurchaseSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Selecciona el item a comprar", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        item_key = self.values[0]
        if item_key == "none":
            await interaction.response.send_message("No hay items disponibles para comprar.", ephemeral=True)
            return
        user_data = get_user(interaction.user.id)
        if user_data["level"] < ITEMS[item_key]["level"]:
            await interaction.response.send_message("Todavía no desbloqueaste eso manin.", ephemeral=True)
            return
        current_count = user_data["shop"].get(item_key, 0)
        if item_key == "amulet" and current_count >= ITEMS["amulet"].get("max", 5):
            await interaction.response.send_message("Ya alcanzaste el máximo de 🪬's.", ephemeral=True)
            return
        price = get_item_price(item_key, current_count)
        if user_data["lomitos"] < price:
            await interaction.response.send_message("No tenés suficientes🌯, broke man.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"¿Vas a comprar **{ITEMS[item_key]['name']}** por **{price}🌯**?",
            view=ConfirmPurchaseView(item_key, price),
            ephemeral=False
        )
class PurchaseView(discord.ui.View):
    def __init__(self, user_data):
        super().__init__(timeout=60)
        options = []
        for key, info in ITEMS.items():
            if user_data["level"] >= info["level"]:
                options.append(discord.SelectOption(label=info["name"], value=key))
        if not options:
            options.append(discord.SelectOption(label="No hay items disponibles", value="none"))
        self.add_item(PurchaseSelect(options))
@bot.tree.command(name="biggie", description="Comprar items de la tienda")
async def biggie(interaction: discord.Interaction):
    user_data = get_user(interaction.user.id)
    view = PurchaseView(user_data)
    await interaction.response.send_message("¿Qué vas a comprar?", view=view, ephemeral=False)
    msg = await interaction.original_response()
    asyncio.create_task(delete_after(msg, 30))
# ---------------------------
# /usarit 
# ---------------------------
class UseItemSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Selecciona el item q vas a usar", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        if selected == "none":
            await interaction.response.send_message("No tenés items para usar amor", ephemeral=True)
            return
        await interaction.response.send_message(f"¿Querés usar {selected}?", view=ConfirmUseView(selected), ephemeral=True)
class UseItemView(discord.ui.View):
    def __init__(self, user_data):
        super().__init__(timeout=60)
        options = []
        for item, count in user_data.get("inventory", {}).items():
            if count > 0:
                options.append(discord.SelectOption(label=f"{item} (x{count})", value=item))
        if not options:
            options.append(discord.SelectOption(label="No tenés items", value="none"))
        self.add_item(UseItemSelect(options))
# ---------------------------
# Confirmar uso de item
# ---------------------------
class ConfirmUseView(discord.ui.View):
    def __init__(self, item_name):
        super().__init__(timeout=30)
        self.item_name = item_name
    @discord.ui.button(label="Usar", style=discord.ButtonStyle.green)
    async def use_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_data = get_user(interaction.user.id)
        inv = user_data.get("inventory", {})
        if inv.get(self.item_name, 0) < 1:
            try:
                await interaction.message.delete()
            except Exception:
                pass
            await interaction.followup.send("No tenés ese item.", ephemeral=True)
            return
        try:
            await interaction.message.delete()
        except Exception:
            pass
        respuesta = ""
        leveled_up = False 

        if self.item_name == "Cliente👦🏼":
            produccion = user_data["shop"].get("lomitero", 0) * (1 + user_data["shop"].get("lomiteria", 0))
            user_data["lomitos"] += produccion
            respuesta = f"Se generaron **{produccion}🌯**"
        elif self.item_name == "buffeo de lomiteros🆙":
            user_data["buffeo_until"] = time.time() + 24 * 3600
            respuesta = "Tus lomiteros generan el doble por 24 horas"
        elif self.item_name == "xp extra✅":
            xp_objetivo = 40 * user_data["level"]
            bonus = int(0.15 * xp_objetivo)
            user_data["xp"] += bonus
            respuesta = f"Se añadieron **{bonus} de XP**"
            if leveled_up:
                respuesta += f"\n subiste al nivel **{user_data['level']}**"
        elif self.item_name == "lomiteria de alquiler🚨":
            user_data["extra_lomiteria_until"] = time.time() + 24 * 3600
            user_data["extra_lomiteria_bonus"] = 5
            respuesta = "Tenés **5** lomiterias extra por **24 horas**"
        elif self.item_name == "salto temporal⏰":
            user_data["last_sueldo"] = 0
            respuesta = "El cooldown de **/sueldo** se reseteó."
        elif self.item_name == "reclutar lomitero👨🏿‍🍳":
            user_data["shop"]["lomitero"] = user_data["shop"].get("lomitero", 0) + 1
            respuesta = "reclutaste un **lomitero👨🏿‍🍳** gratis."
        elif self.item_name == "caramelo raro🍬":
            user_data["level"] += 1
            respuesta = f"SUBISTE AL NIVEL **{user_data['level']}** BOLUDO"
        elif self.item_name == "lomiteria gratis🏪":
            user_data["shop"]["lomiteria"] = user_data["shop"].get("lomiteria", 0) + 1
            respuesta = "ahora tenés una **lomiteria🏪** más gratis."
        elif self.item_name == "lomicoincita🦛":
            user_data["lomitos"] += 1000000
            respuesta = "anda a cagar, ganaste **1,000,000🌯** boludo"
        elif self.item_name == "mortero bala🧑🏿‍🦲":
            user_data["lomitos"] += 10000000
            respuesta = "na bueno"
        else:
            respuesta = "Item desconocido."

        inv[self.item_name] -= 1
        if inv[self.item_name] <= 0:
            del inv[self.item_name]
        user_data["inventory"] = inv
        save_data()

        await interaction.followup.send(respuesta, ephemeral=True)

    @discord.ui.button(label="Mejor no", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.message.delete()
        except Exception:
            pass
        await interaction.response.send_message("Operación cancelada.", ephemeral=True)
@bot.tree.command(name="usarit", description="Usa un item de tu inventario")
async def usarit(interaction: discord.Interaction):
    user_data = get_user(interaction.user.id)
    view = UseItemView(user_data)
    await interaction.response.send_message("¿Qué item queres usar?", view=view, ephemeral=True)
# ---------------------------
# /itinfo
# ---------------------------
@bot.tree.command(name="itinfo", description="Muestra la info y probabilidades de los items de suerte")
async def itinfo(interaction: discord.Interaction):
    desc = (
        "**xp extra✅:** 30%\n"
        "**Cliente👦🏼:** 20%\n"
        "**buffeo de lomiteros🆙:** 20%\n"
        "**salto temporal⏰:** 10%\n"
        "**lomiteria de alquiler🚨:** 7%\n"
        "**reclutar lomitero👨🏿‍🍳:** 5%\n"
        "**caramelo raro🍬:** 5%\n"
        "**lomiteria gratis🏪:** 2.4%\n"
        "**lomicoincita🦛:** 0.5%\n"
        "**mortero bala🧑🏿‍🦲:** 0.1%"
    )
    embed = discord.Embed(title="rates drop de items", description=desc, color=0x00ff00)
    await interaction.response.send_message(embed=embed, ephemeral=False)
    msg = await interaction.original_response()
    asyncio.create_task(delete_after(msg, 40))
# ---------------------------
# /nivel
# ---------------------------
@bot.tree.command(name="nivel", description="Muestra el nivel de un usuario")
@app_commands.describe(miembro="ver el nivel de alguien más")
async def nivel(interaction: discord.Interaction, miembro: discord.Member = None):
    target = miembro if miembro else interaction.user
    user_data = get_user(target.id)
    current_level = user_data["level"]
    current_xp = user_data.get("xp", 0)
    xp_needed = 40 * current_level
    xp_remaining = xp_needed - current_xp
    embed = discord.Embed(color=0x00ffff)
    embed.title = "Fichita :3"
    embed.description = (
        f"{target.mention} sos **nivel {current_level}**\n\n"
        f"Tenés **{current_xp}/{xp_needed}** de XP\n\n"
        f"Necesitás **{xp_remaining}** XP más para subir de nivel\n"
    )
    if target.display_avatar:
        embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=True)
    )
# ---------------------------
# /donar
# ---------------------------
@bot.tree.command(name="donar", description="Donar 🌯 a otros negris")
@app_commands.describe(miembro="a quien vas a donar amor?", cantidad="cuántos 🌯 vas a donar?")
async def donar(interaction: discord.Interaction, miembro: discord.Member, cantidad: int):
    if cantidad <= 0:
        await interaction.response.send_message("La cantidad tiene q ser positiva boludo", ephemeral=True)
        return
    sender = get_user(interaction.user.id)
    receiver = get_user(miembro.id)
    if sender["lomitos"] < cantidad:
        await interaction.response.send_message("broke ass niga😂", ephemeral=True)
        return
    sender["lomitos"] -= cantidad
    sender["donado"] = sender.get("donado", 0) + cantidad
    receiver["lomitos"] += cantidad
    receiver["recibido"] = receiver.get("recibido", 0) + cantidad
    save_data()
    await interaction.response.send_message(f"<@{interaction.user.id}> donó **{cantidad}**🌯 a <@{miembro.id}>", ephemeral=False)
# ---------------------------
# /pinfo
# ---------------------------
@bot.tree.command(name="pinfo", description="Muestra tu perfil y stats")
async def pinfo(interaction: discord.Interaction):
    user_data = get_user(interaction.user.id)
    shop = user_data.get("shop", {})
    hourly_production = compute_hourly_production(user_data)
    total_lomitos = user_data['lomitos']
    nivel = user_data['level']
    donado = user_data.get('donado', 0)
    recibido = user_data.get('recibido', 0)
    # Detectamos si hay algún buff activo que afecte la producción horaria
    buff_activo = (user_data.get("buffeo_until", 0) > time.time() or 
                   user_data.get("extra_lomiteria_until", 0) > time.time())
    # Si hay buff activo, usamos un bloque diff para mostrar el número en verde
    if buff_activo:
        prod_str = f"```diff\n+ {hourly_production}🌯\n```"
    else:
        prod_str = f"{hourly_production}🌯"

    embed = discord.Embed(title=f"info de {interaction.user.display_name}", color=0x00ffff)
    if interaction.user.display_avatar:
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
    desc = (
        f"**Tiene en total** {total_lomitos}🌯\n\n"
        f"**Nivel:** {nivel}\n\n"
        f"**Producción p/h:** {prod_str}\n\n"
        f"**Donado** {donado}🌯 | **Recibido** {recibido}🌯\n\n"
    )
    embed.description = desc

    shop_info = (
        f"👨🏿‍🍳 Lomiteros: **{shop.get('lomitero', 0)}**\n"
        f"🏪 Lomiterias: **{shop.get('lomiteria', 0)}**\n"
        f"🪬 Amuletos: **{shop.get('amulet', 0)}**\n"
        f"🦛 Hipopotamos: **{shop.get('hipopotamo', 0)}**\n"
        f"👳🏽‍♂️ Árabes: **{shop.get('arabe', 0)}**\n"
        f"🕌 Mezquitas: **{shop.get('mezquita', 0)}**"
    )
    embed.add_field(name="Cosas Compradas:", value=shop_info, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=False)
# ---------------------------
# Lógica de Blackjack
# ---------------------------
def draw_card():
    ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
    card = random.choice(ranks)
    if card in ['J', 'Q', 'K']:
        value = 10
    elif card == 'A':
        value = 11
    else:
        value = int(card)
    return card, value
def calculate_hand_value(cards):
    total = sum(value for card, value in cards)
    aces = sum(1 for card, value in cards if card == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total
@bot.tree.command(name="blackjack", description="jugá al blackjack apostando 🌯")
@app_commands.describe(apuesta="Cantidad de 🌯 a apostar")
async def blackjack(interaction: discord.Interaction, apuesta: int):
    user_data = get_user(interaction.user.id)
    if apuesta <= 0 or user_data["lomitos"] < apuesta:
        await interaction.response.send_message("???", ephemeral=True)
        return
    user_data["lomitos"] -= apuesta
    player_cards = [draw_card(), draw_card()]
    dealer_cards = [draw_card(), draw_card()]
    player_total = calculate_hand_value(player_cards)
    dealer_total = calculate_hand_value(dealer_cards)
    while player_total < 17:
        player_cards.append(draw_card())
        player_total = calculate_hand_value(player_cards)
        if player_total > 21:
            break
    while dealer_total < 17:
        dealer_cards.append(draw_card())
        dealer_total = calculate_hand_value(dealer_cards)
    result = ""
    if player_total > 21:
        result = "Te pasaste. Perdiste."
    elif dealer_total > 21 or player_total > dealer_total:
        winnings = apuesta * 2
        user_data["lomitos"] += winnings
        result = f"Ganaste **{winnings}🌯** negri"
    elif player_total == dealer_total:
        user_data["lomitos"] += apuesta
        result = "Empataste, nt"
    else:
        result = "Perdiste😂😂😂"
    save_data()
    final_balance = f"Ahora tenés **{user_data['lomitos']}🌯**"
    desc = (
        f"**Tu mano:** {', '.join(card for card, value in player_cards)} (Total: {player_total})\n"
        f"**Mano del dealer:** {', '.join(card for card, value in dealer_cards)} (Total: {dealer_total})\n\n"
        f"{result}\n{final_balance}"
    )
    await interaction.response.send_message(desc)
# ---------------------------
# /gamble
# ---------------------------
@bot.tree.command(name="gamble", description="apostá 🌯, igual es medio imposible ganar negri, pero vos mandale")
@app_commands.describe(cantidad="Cantidad a apostar")
async def gamble(interaction: discord.Interaction, cantidad: int):
    user_data = get_user(interaction.user.id)
    if cantidad <= 0 or user_data["lomitos"] < cantidad:
        await interaction.response.send_message("no tenes plata manin😂", ephemeral=True)
        return
    user_data["lomitos"] -= cantidad
    if random.random() < 0.7:
        result = f"Perdiste **{cantidad}🌯**"
    else:
        winnings = cantidad * 2
        user_data["lomitos"] += winnings
        result = f"BIEN KAPELU, GANASTE **{winnings}🌯**"
    save_data()
    final_balance = f"Ahora tenés **{user_data['lomitos']}🌯**"
    await interaction.response.send_message(f"{result}\n{final_balance}")
# ---------------------------
# /update
# ---------------------------
@bot.tree.command(name="update", description="Enviar un mensaje de update al canal de updates")
@app_commands.describe(mensaje="El mensaje de update (usa '\\n' para saltos de línea)")
async def update(interaction: discord.Interaction, mensaje: str):
    if interaction.user.id != 559487297234665480:
        await interaction.response.send_message("No tenes permiso para usar este comando.", ephemeral=True)
        return
    mensaje = mensaje.replace("\\n", "\n")
    channel = discord.utils.get(interaction.guild.text_channels, name="updateslomicoincito")
    if channel is None:
        await interaction.response.send_message("No se encontró el canal 'updateslomicoincito'.", ephemeral=True)
        return
    await channel.send(mensaje)
    await interaction.response.send_message("Update enviado.", ephemeral=True)
# ---------------------------
# /ranks (nuevo comando unificado)
# ---------------------------
class RankingSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Más millonarios", description="Ranking por cantidad de 🌯", emoji="🌯"),
            discord.SelectOption(label="Más leveados", description="Ranking por nivel", emoji="🎚️")
        ]
        super().__init__(placeholder="q ranking queres ver", options=options, min_values=1, max_values=1)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected = self.values[0]
        guild = interaction.guild
        if selected == "Más millonarios":
            sorted_users = sorted(data.items(), key=lambda x: x[1]["lomitos"], reverse=True)
            title = "Ranking de los más millonarios"
            desc = ""
            top_member_avatar_url = None 
            for i, (uid, udata) in enumerate(sorted_users[:10], 1):
                try:
                    member = await guild.fetch_member(int(uid))
                    nombre = f"**{member.display_name}**"
                    if i == 1: 
                        top_member_avatar_url = member.display_avatar.url if member.display_avatar else None
                except:
                    nombre = "**Usuario desconocido**"
                desc += f"#**{i}** - {nombre}\n**Con {udata['lomitos']}**🌯\n\n"
            embed = discord.Embed(title=title, description=desc, color=0xFFD700)
            if top_member_avatar_url: 
                embed.set_thumbnail(url=top_member_avatar_url)
            await interaction.followup.send(embed=embed)
        else:
            sorted_users = sorted(data.items(), key=lambda x: x[1]["level"], reverse=True)
            title = "Ranking de los más leveados"
            desc = ""
            top_member_avatar_url = None 
            for i, (uid, udata) in enumerate(sorted_users[:10], 1):
                try:
                    member = await guild.fetch_member(int(uid))
                    nombre = f"**{member.display_name}**"
                    if i == 1: 
                        top_member_avatar_url = member.display_avatar.url if member.display_avatar else None
                except:
                    nombre = "**Usuario desconocido**"
                desc += f"#**{i}** - {nombre}\n**Nivel {udata['level']}**\n\n"
            embed = discord.Embed(title=title, description=desc, color=0x00FF00)
            if top_member_avatar_url: 
                embed.set_thumbnail(url=top_member_avatar_url)
            await interaction.followup.send(embed=embed)
@bot.tree.command(name="ranks", description="Muestra los rankings del servidor")
async def ranks(interaction: discord.Interaction):
    view = discord.ui.View()
    view.add_item(RankingSelect())
    await interaction.response.send_message("selecciona el tipo de ranking:", view=view)
# ---------------------------
# in bot
# ---------------------------
load_data()
webserver.keep_alive()
bot.run(DISCORD_TOKEN)


