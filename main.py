from flask import Flask
import logging
from telegram import Update, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)
import asyncio

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7983937804:AAEhm1FoXrNL3QoDwh24D7_TZsHnSCIPVIo"
CREATOR_USERNAME = "@Reku_Senpai"

players = {}
BASE_PN_LEVEL = 5000
admins = set()
events = []  # Liste des événements sous forme [(nom, description)]

def is_creator(update: Update):
    user = update.effective_user
    return user and (user.username and user.username.lower() == CREATOR_USERNAME.lstrip('@').lower())

def is_admin(update: Update):
    user = update.effective_user
    return is_creator(update) or (user and user.id in admins)

def get_player(user):
    user_id = user.id
    if user_id not in players:
        players[user_id] = {
            "username": user.username or user.first_name,
            "pn": 0,
            "pieces": 0,
            "coupes": 0,
            "fables": [],
            "guilde": "Aucune",
            "niveau": 1,
            "experience": 0,
            "statut": "",
            "inscription": "",
            "activite": [],
            "saved_stats": None,
            "is_admin": False,
        }
    return players[user_id]

def calculate_next_level_pn(level):
    return BASE_PN_LEVEL + (level - 1) * 10000

def check_and_update_level(player):
    leveled_up = False
    # Ajout support régression si pn trop bas
    while True:
        current_level = player.get("niveau", 1)
        pn = player.get("pn", 0)
        next_level_pn = calculate_next_level_pn(current_level)
        if pn >= next_level_pn:
            player["niveau"] = current_level + 1
            leveled_up = True
        elif current_level > 1 and pn < calculate_next_level_pn(current_level - 1):
            player["niveau"] = current_level - 1
            leveled_up = True
        else:
            break
    return leveled_up

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = get_player(user)
    if not player["inscription"]:
        from datetime import datetime
        player["inscription"] = datetime.now().strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"👋 Bienvenue {user.first_name} ! Ton profil a été créé. Utilise /profil pour voir tes stats.\n"
        "Attention : la commande /commandes est disponible uniquement en message privé au bot."
    )

# --- PROFIL INTERACTIF ---

def build_profile_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("Fables", callback_data="profil_fables")],
        [InlineKeyboardButton("Pièces", callback_data="profil_pieces")],
        [InlineKeyboardButton("Coupes", callback_data="profil_coupes")],
        [InlineKeyboardButton("PN", callback_data="profil_pn")],
        [InlineKeyboardButton("Guilde", callback_data="profil_guilde")],
        [InlineKeyboardButton("Statut", callback_data="profil_statut")],
        [InlineKeyboardButton("Close", callback_data="profil_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_back_close_keyboard():
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="profil_back")],
        [InlineKeyboardButton("Close", callback_data="profil_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_profile_page(update: Update, context: ContextTypes.DEFAULT_TYPE, user, page="main"):
    player = get_player(user)
    photos = await context.bot.get_user_profile_photos(user.id, limit=1)
    photo_file_id = photos.photos[0][0].file_id if photos.total_count > 0 else None

    if player.get("is_admin", False):
        pn = "Administrateur"
        pieces = "Administrateur"
        coupes = "Administrateur"
        niveau = "Administrateur"
        statut = "Administrateur"
        guilde = "CABINET DES OMBRES"
        fables = ["Toutes"]
        inscription = "∞"
    elif user.username and user.username.lower() == CREATOR_USERNAME.lstrip('@').lower():
        pn = "∞"
        pieces = "∞"
        coupes = "∞"
        niveau = "∞"
        statut = "Créateur du bot"
        guilde = "CABINET DES OMBRES"
        fables = ["Toutes"]
        inscription = "∞"
    else:
        pn = player.get("pn", 0)
        pieces = player.get("pieces", 0)
        coupes = player.get("coupes", 0)
        niveau = player.get("niveau", 1)
        statut = player.get("statut", "")
        guilde = player.get("guilde", "Aucune")
        fables = player.get("fables", [])
        inscription = player.get("inscription", "inconnu")

    if page == "main":
        profil_text = (
            f"👤 Profil de {user.first_name} (@{user.username or 'inconnu'})\n"
            f"🏆 Niveau : {niveau}\n"
            f"📅 Inscrit depuis : {inscription}\n\n"
            f"Utilise les boutons pour voir plus de détails."
        )
        keyboard = build_profile_main_keyboard()
    elif page == "fables":
        fables_text = "• " + "\n• ".join(fables) if fables else "Aucune"
        profil_text = f"📚 Fables :\n{fables_text}\n\nPour retirer une fable, utilise la commande /deleteFable en réponse."
        keyboard = build_back_close_keyboard()
    elif page == "pieces":
        profil_text = f"💰 Pièces : {pieces}\n\nÉchangeables entre joueurs via /trade."
        keyboard = build_back_close_keyboard()
    elif page == "coupes":
        profil_text = f"🏆 Coupes : {coupes}\n\nÉchangeables entre joueurs via /trade."
        keyboard = build_back_close_keyboard()
    elif page == "pn":
        if isinstance(pn, int):
            next_level_pn = calculate_next_level_pn(player.get("niveau",1))
            pn_missing = max(0, next_level_pn - pn)
            profil_text = (
                f"🥇 Points de Niveau (PN) : {pn}\n"
                f"🧭 PN nécessaires pour le niveau suivant ({player.get('niveau',1)+1}) : {next_level_pn}\n"
                f"⚠️ Il te manque {pn_missing} PN pour monter de niveau."
            )
        else:
            profil_text = f"🥇 Points de Niveau (PN) : {pn}"
        keyboard = build_back_close_keyboard()
    elif page == "guilde":
        profil_text = f"🛡️ Guilde : {guilde}\n\nPour changer ta guilde, contacte un administrateur."
        keyboard = build_back_close_keyboard()
    elif page == "statut":
        profil_text = f"📜 Statut : {statut if statut else 'Aucun'}\n\nPour modifier ton statut, contacte un administrateur."
        keyboard = build_back_close_keyboard()
    else:
        profil_text = "Erreur : page inconnue."
        keyboard = build_back_close_keyboard()

    if update.callback_query:
        try:
            await update.callback_query.edit_message_caption(caption=profil_text, reply_markup=keyboard)
        except:
            await update.callback_query.edit_message_text(text=profil_text, reply_markup=keyboard)
    else:
        if photo_file_id:
            await update.message.reply_photo(photo=photo_file_id, caption=profil_text, reply_markup=keyboard)
        else:
            await update.message.reply_text(profil_text, reply_markup=keyboard)

async def profil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # On sauvegarde l'id du joueur qui ouvre le profil pour gérer interaction boutons
    context.user_data["profil_user_id"] = user.id
    await send_profile_page(update, context, user, page="main")

async def profile_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    profil_user_id = context.user_data.get("profil_user_id")

    # Si pas d'ID enregistré, initialiser à l'utilisateur courant
    if profil_user_id is None:
        profil_user_id = query.from_user.id
        context.user_data["profil_user_id"] = profil_user_id

    # Gestion stricte d'accès : seul le propriétaire ou le créateur peuvent interagir
    if query.from_user.id != profil_user_id and not is_creator(update):
        # Ignorer la tentative et envoyer la fenêtre de profil de l'utilisateur qui a cliqué
        await query.answer(
            f"❌ Tu n'as pas accès aux informations du profil demandé.\n"
            "Je t'envoie ta propre fenêtre de profil à la place.",
            show_alert=True
        )
        # Envoi nouveau profil personnalisé à l'utilisateur qui a cliqué
        await send_profile_page(update, context, query.from_user, page="main")
        return

    if data == "profil_close":
        try:
            await query.message.delete()
        except:
            pass
        context.user_data.pop("profil_user_id", None)
        return
    elif data == "profil_back":
        user_obj = await context.bot.get_chat(profil_user_id)
        await send_profile_page(update, context, user_obj, page="main")
    else:
        page = data.replace("profil_", "")
        user_obj = await context.bot.get_chat(profil_user_id)
        await send_profile_page(update, context, user_obj, page=page)

# --- FIN PROFIL INTERACTIF ---

async def classement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user

    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        if target_user.username and target_user.username.lower() == CREATOR_USERNAME.lstrip('@').lower():
            await update.message.reply_text(f"Ce joueur est au dessus du classement.")
            return
        player = get_player(target_user)
        rank_list = sorted(
            [(uid, p) for uid, p in players.items() if uid != user.id and p.get("niveau", 1) != "Administrateur"],
            key=lambda x: x[1].get("niveau", 1), reverse=True
        )
        rank = next((i + 1 for i, (uid, p) in enumerate(rank_list) if uid == target_user.id), None)
        if rank is None:
            await update.message.reply_text(f"Ce joueur est au dessus du classement.")
            return
        await update.message.reply_text(
            f"Classement de {target_user.first_name} :\n"
            f"Niveau : {player.get('niveau')}\n"
            f"PN : {player.get('pn')}\n"
            f"Pièces : {player.get('pieces')}\n"
            f"Coupes : {player.get('coupes')}\n"
            f"Guilde : {player.get('guilde')}\n"
            f"Statut : {player.get('statut') or 'Aucun'}\n"
        )
        return

    # Classement global
    classement_text = "🏆 Classement des joueurs (par niveau décroissant) :\n\n"
    classement_list = sorted(
        [(uid, p) for uid, p in players.items() if p.get("username", "").lower() != CREATOR_USERNAME.lstrip('@').lower()],
        key=lambda x: x[1].get("niveau", 1), reverse=True
    )
    for i, (uid, p) in enumerate(classement_list, start=1):
        classement_text += (
            f"{i}. {p.get('username', 'inconnu')} - Niveau {p.get('niveau', 1)} - PN {p.get('pn', 0)} - "
            f"Pièces {p.get('pieces', 0)} - Coupes {p.get('coupes', 0)} - Guilde {p.get('guilde', 'Aucune')}\n"
        )
    await update.message.reply_text(classement_text)

# --- LISTE DES JOUEURS ---

async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not players:
        await message.reply_text("Aucun joueur n'a encore lancé le bot.")
        return

    texte = "👥 Liste des joueurs ayant lancé le bot :\n\n"
    for uid, p in players.items():
        if p.get("username", "").lower() == CREATOR_USERNAME.lstrip('@').lower():
            continue
        texte += (
            f"• {p.get('username','inconnu')} - Niveau {p.get('niveau',1)} - PN {p.get('pn',0)} - "
            f"Pièces {p.get('pieces',0)} - Coupes {p.get('coupes',0)} - Guilde {p.get('guilde','Aucune')} - "
            f"Statut {p.get('statut','Aucun')}\n"
        )
    await message.reply_text(texte)

# --- COMMANDES POUR LES FABLES, STATUT, GUILDE ---

async def fable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre à un message d'un joueur pour lui attribuer une fable.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Tu dois préciser le nom de la fable.")
        return
    fable_name = " ".join(args)
    user = update.message.reply_to_message.from_user
    player = get_player(user)
    if fable_name in player["fables"]:
        await update.message.reply_text(f"Le joueur a déjà la fable '{fable_name}'.")
        return
    player["fables"].append(fable_name)
    await update.message.reply_text(f"Fable '{fable_name}' ajoutée à {user.first_name}.")

async def deleteFable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre au message du joueur pour supprimer une fable.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Tu dois préciser le nom de la fable à supprimer.")
        return
    fable_name = " ".join(args)
    user = update.message.reply_to_message.from_user
    player = get_player(user)
    if fable_name not in player["fables"]:
        await update.message.reply_text(f"Le joueur ne possède pas la fable '{fable_name}'.")
        return
    player["fables"].remove(fable_name)
    await update.message.reply_text(f"Fable '{fable_name}' supprimée de {user.first_name}.")

async def statut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre à un message d'un joueur pour lui attribuer un statut.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Tu dois préciser le nom du statut.")
        return
    statut_name = " ".join(args)
    user = update.message.reply_to_message.from_user
    player = get_player(user)
    player["statut"] = statut_name
    await update.message.reply_text(f"Statut '{statut_name}' attribué à {user.first_name}.")

async def deleteStatut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre au message du joueur pour supprimer son statut.")
        return
    user = update.message.reply_to_message.from_user
    player = get_player(user)
    player["statut"] = ""
    await update.message.reply_text(f"Statut supprimé pour {user.first_name}.")

# --- GUILDE ---

async def guilde(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre à un message d'un joueur pour lui attribuer une guilde.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Tu dois préciser le nom de la guilde.")
        return
    guilde_name = " ".join(args)
    user = update.message.reply_to_message.from_user
    player = get_player(user)
    player["guilde"] = guilde_name
    await update.message.reply_text(f"Guilde '{guilde_name}' attribuée à {user.first_name}.")

async def deleteGuilde(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre au message du joueur pour supprimer sa guilde.")
        return
    user = update.message.reply_to_message.from_user
    player = get_player(user)
    player["guilde"] = "Aucune"
    await update.message.reply_text(f"Guilde supprimée pour {user.first_name}.")

# --- ÉCHANGE ENTRE JOUEURS ---

async def trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user = update.effective_user

    if not message.reply_to_message:
        await message.reply_text("Tu dois répondre au message du joueur avec qui tu veux échanger.")
        return

    args = context.args
    if len(args) < 2:
        await message.reply_text("Usage : /trade [quantité] [pièces/coupes]")
        return

    try:
        quantite = int(args[0])
        if quantite <= 0:
            await message.reply_text("La quantité doit être un entier positif.")
            return
    except:
        await message.reply_text("La quantité doit être un nombre entier.")
        return

    ressource = args[1].lower()
    if ressource not in ["pièces", "pieces", "coupes"]:
        await message.reply_text("La ressource doit être 'pièces' ou 'coupes'.")
        return

    player_from = get_player(user)
    player_to = get_player(message.reply_to_message.from_user)

    if ressource in ["pièces", "pieces"]:
        if player_from["pieces"] < quantite:
            await message.reply_text("Tu n'as pas assez de pièces.")
            return
        player_from["pieces"] -= quantite
        player_to["pieces"] += quantite
        await message.reply_text(f"Tu as envoyé {quantite} pièces à {message.reply_to_message.from_user.first_name}.")
    elif ressource == "coupes":
        if player_from["coupes"] < quantite:
            await message.reply_text("Tu n'as pas assez de coupes.")
            return
        player_from["coupes"] -= quantite
        player_to["coupes"] += quantite
        await message.reply_text(f"Tu as envoyé {quantite} coupes à {message.reply_to_message.from_user.first_name}.")

# --- ADMINISTRATION ---

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre au message du joueur à nommer admin.")
        return

    user = update.message.reply_to_message.from_user
    player = get_player(user)

    if player.get("is_admin", False):
        await update.message.reply_text(f"{user.first_name} est déjà administrateur.")
        return

    # Sauvegarde des stats avant passage admin
    player["saved_stats"] = {
        "pn": player.get("pn", 0),
        "pieces": player.get("pieces", 0),
        "coupes": player.get("coupes", 0),
        "niveau": player.get("niveau", 1),
        "statut": player.get("statut", ""),
        "guilde": player.get("guilde", "Aucune"),
        "fables": player.get("fables", [])[:],
    }

    player["is_admin"] = True
    admins.add(user.id)
    # Mise à jour stats admin
    player["pn"] = "Administrateur"
    player["pieces"] = "Administrateur"
    player["coupes"] = "Administrateur"
    player["niveau"] = "Administrateur"
    player["statut"] = "Administrateur"
    player["guilde"] = "CABINET DES OMBRES"
    player["fables"] = ["Toutes"]
    await update.message.reply_text(f"{user.first_name} est maintenant administrateur.")

async def unadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Tu dois répondre au message du joueur pour lui retirer le statut admin.")
        return

    user = update.message.reply_to_message.from_user
    player = get_player(user)

    if not player.get("is_admin", False):
        await update.message.reply_text(f"{user.first_name} n'est pas administrateur.")
        return

    saved = player.get("saved_stats")
    if saved:
        player["pn"] = saved.get("pn", 0)
        player["pieces"] = saved.get("pieces", 0)
        player["coupes"] = saved.get("coupes", 0)
        player["niveau"] = saved.get("niveau", 1)
        player["statut"] = saved.get("statut", "")
        player["guilde"] = saved.get("guilde", "Aucune")
        player["fables"] = saved.get("fables", [])
        player["saved_stats"] = None
    player["is_admin"] = False
    admins.discard(user.id)
    await update.message.reply_text(f"{user.first_name} n'est plus administrateur.")

# --- COMMANDES ---

async def commandes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.chat.type != "private":
        await update.message.reply_text("La commande /commandes est uniquement utilisable en message privé.")
        return

    if is_creator(update):
        texte = (
            "📜 Liste complète des commandes disponibles (créateur) :\n\n"
            "/start - Démarrer le bot\n"
            "/profil - Voir votre profil\n"
            "/classement - Voir le classement\n"
            "/liste - Liste des joueurs\n"
            "/fable - Ajouter une fable (réponse + nom) (créateur)\n"
            "/deleteFable - Supprimer une fable (réponse + nom) (créateur)\n"
            "/statut - Ajouter un statut (réponse + nom) (créateur)\n"
            "/deleteStatut - Supprimer statut (réponse) (créateur)\n"
            "/guilde - Ajouter une guilde (réponse + nom) (créateur)\n"
            "/deleteGuilde - Supprimer guilde (réponse) (créateur)\n"
            # "/add - Ajouter PN/pièces/coupes (réponse + quantité + ressource) (créateur)\n"
            # "/delete - Retirer PN/pièces/coupes (réponse + quantité + ressource) (créateur)\n"
            "/trade - Échanger pièces/coupes (réponse + quantité + ressource)\n"
            "/admin - Nommer administrateur (réponse) (créateur)\n"
            "/unadmin - Retirer admin (réponse) (créateur)\n"
            "/event - Ajouter un événement (/event nom, description) (créateur)\n"
            "/deleteEvent - Supprimer un événement (/deleteEvent nom, description) (créateur)\n"
            "/show - Afficher les événements\n"
        )
    else:
        texte = (
            "📜 Liste des commandes disponibles :\n\n"
            "/start - Démarrer le bot\n"
            "/profil - Voir votre profil\n"
            "/classement - Voir le classement\n"
            "/liste - Liste des joueurs\n"
            "/trade - Échanger pièces/coupes (réponse + quantité + ressource)\n"
            "/show - Afficher les événements\n"
        )
    await update.message.reply_text(texte)

# --- GESTION DES ÉVÉNEMENTS ---

async def event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return

    args_text = update.message.text[len("/event"):].strip()
    if not args_text:
        await update.message.reply_text("Usage : /event [nom de l'événement], [description]")
        return
    if ',' not in args_text:
        await update.message.reply_text("Format incorrect. Utilise : /event nom, description")
        return

    nom, description = map(str.strip, args_text.split(',', 1))

    # Vérifie si événement existe déjà
    for e in events:
        if e[0].lower() == nom.lower():
            await update.message.reply_text(f"Un événement avec ce nom existe déjà.")
            return

    events.append((nom, description))
    await update.message.reply_text(f"Événement '{nom}' ajouté.")

async def deleteEvent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_creator(update):
        await update.message.reply_text("Commande réservée au créateur.")
        return

    args_text = update.message.text[len("/deleteEvent"):].strip()
    if not args_text:
        await update.message.reply_text("Usage : /deleteEvent [nom de l'événement], [description]")
        return
    if ',' not in args_text:
        await update.message.reply_text("Format incorrect. Utilise : /deleteEvent nom, description")
        return

    nom, description = map(str.strip, args_text.split(',', 1))

    for i, e in enumerate(events):
        if e[0].lower() == nom.lower() and e[1] == description:
            events.pop(i)
            await update.message.reply_text(f"Événement '{nom}' supprimé.")
            return
    await update.message.reply_text("Aucun événement correspondant trouvé.")

async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not events:
        await update.message.reply_text("Aucun événement enregistré actuellement.")
        return
    texte = "📅 Événements en cours :\n\n"
    for nom, desc in events:
        texte += f"🔹 {nom}\n{desc}\n\n"
    await update.message.reply_text(texte)

# --- HANDLERS ET DÉMARRAGE ---

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("profil", profil))
    application.add_handler(CallbackQueryHandler(profile_button_handler, pattern="^profil_"))
    application.add_handler(CommandHandler("classement", classement))
    application.add_handler(CommandHandler("commandes", commandes))
    application.add_handler(CommandHandler("liste", liste))

    application.add_handler(CommandHandler("fable", fable))
    application.add_handler(CommandHandler("deleteFable", deleteFable))
    application.add_handler(CommandHandler("statut", statut))
    application.add_handler(CommandHandler("deleteStatut", deleteStatut))
    application.add_handler(CommandHandler("guilde", guilde))
    application.add_handler(CommandHandler("deleteGuilde", deleteGuilde))

    # application.add_handler(CommandHandler("add", add))  # Non défini, retiré
    # application.add_handler(CommandHandler("delete", delete))  # Non défini, retiré
    application.add_handler(CommandHandler("trade", trade))

    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("unadmin", unadmin))

    application.add_handler(CommandHandler("event", event))
    application.add_handler(CommandHandler("deleteEvent", deleteEvent))
    application.add_handler(CommandHandler("show", show))

    application.run_polling()

if __name__ == "__main__":
    main()
