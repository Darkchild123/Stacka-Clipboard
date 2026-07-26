# ============================================================
# Stacka - i18n.py
# ============================================================
# Lightweight in-app UI translation.
#
#   tr("English text")  ->  the active language's string, or the English
#   text unchanged when there's no translation. So anything we don't
#   translate simply stays English ("not everything needs translating").
#
# The active language is a plain module-level code ("en", "fr", ...).
# SettingsPanel sets it from the saved config value and re-renders on change;
# main.py initialises it at startup. Keys are the EXACT English UI strings —
# emoji and spacing are kept OUTSIDE tr() where practical (e.g.
# "🎨  " + tr("Appearance")); a few button labels keep the emoji in the key.
#
# Translations are best-effort; a native-speaker pass is recommended before a
# public release, especially for the longer captions and for zh/ko phrasing.
# ============================================================

# (code, endonym) — the endonym (the language's own name) is what the
# dropdown shows, so each language is labelled the way its speakers call it.
LANGUAGES = [
    ("en", "🇬🇧 English"),
    ("fr", "🇫🇷 Français"),
    ("es", "🇪🇸 Español"),
    ("it", "🇮🇹 Italiano"),
    ("ru", "🇷🇺 Русский"),
    ("zh", "🇨🇳 中文"),
    ("ko", "🇰🇷 한국어"),
]

_active = "en"


def available_codes():
    return [c for c, _ in LANGUAGES]


def endonym(code: str) -> str:
    for c, name in LANGUAGES:
        if c == code:
            return name
    return code


def set_language(code: str):
    global _active
    _active = code if code in available_codes() else "en"


def get_language() -> str:
    return _active


def tr(text: str) -> str:
    """Active-language string for `text`, or `text` itself if untranslated."""
    if _active == "en":
        return text
    return _TRANSLATIONS.get(_active, {}).get(text, text)


# _TRANSLATIONS[code][english] = translated.
_TRANSLATIONS = {
    "fr": {
        "Auto-wipe": "Effacement auto",
        "Never": "Jamais",
        "Daily": "Quotidien",
        "Weekly": "Hebdomadaire",
        "Monthly": "Mensuel",
        "Quarterly": "Trimestriel",
        "Yearly": "Annuel",
        "Next:": "Prochain :",
        "Done": "Terminé",
        "History is kept until you clear it yourself.": "L'historique est conservé jusqu'à ce que vous l'effaciez.",
        "Clears every list automatically. Pinned items are kept.": "Efface automatiquement toutes les listes. Les éléments épinglés sont conservés.",
        "Clear your entire clipboard history?": "Effacer tout l'historique du presse-papiers ?",
        "This cannot be undone.": "Cette action est irréversible.",
        # menus / chrome
        "Settings": "Paramètres", "Close": "Fermer",
        "Clear History": "Effacer l'historique", "Quit Stacka": "Quitter Stacka",
        # section headings
        "Appearance": "Apparence", "Sizing": "Taille", "Icon pack": "Pack d'icônes",
        "Popup trigger": "Déclencheur", "Close behaviour": "Fermeture",
        "Shortcuts": "Raccourcis", "History": "Historique", "Profiles": "Profils",
        "About Stacka": "À propos de Stacka",
        # appearance
        "Theme:": "Thème :", "Dark": "Sombre", "Light": "Clair",
        "Popup transparency:": "Transparence :", "Row hover:": "Survol :",
        "Indigo": "Indigo", "Gold": "Or", "Emerald": "Émeraude", "Rose": "Rose",
        "Sky": "Ciel", "Violet": "Violet", "Slate": "Ardoise",
        # sizing
        "10% steps · 100% = default": "pas de 10 % · 100 % = défaut",
        "Row size": "Taille des lignes", "Side list rows": "Lignes du panneau",
        "Font size": "Taille du texte",
        # icon pack
        "🎨  Default Stacka": "🎨  Stacka par défaut",
        "🏷  Labeled documents": "🏷  Documents étiquetés",
        "Colourful modern icons — Office letter tiles, the Python logo, gears, and more.":
            "Icônes modernes et colorées — tuiles Office, logo Python, engrenages, etc.",
        "Document-style icons with the file extension shown as a badge (PDF, DOCX, PNG…), one per extension.":
            "Icônes de type document avec l'extension en badge (PDF, DOCX, PNG…), une par extension.",
        # popup trigger
        "Pick up to two — e.g. overlay button + double right-click. “Hotkey only” can’t be combined.":
            "Choisissez-en jusqu'à deux — p. ex. bouton superposé + double clic droit. « Raccourci seul » ne se combine pas.",
        "🖱  Double right-click": "🖱  Double clic droit",
        "🖱  Middle-click": "🖱  Clic molette",
        "⏪  Mouse side button": "⏪  Bouton latéral",
        "⌨  Ctrl + right-click": "⌨  Ctrl + clic droit",
        "🔘  Overlay button": "🔘  Bouton superposé",
        "⌨  Hotkey only": "⌨  Raccourci seul",
        "Right-click twice quickly to open Stacka at the cursor. One hand, never covers the app's own menu.":
            "Double clic droit rapide pour ouvrir Stacka au curseur. D'une main, sans masquer le menu de l'application.",
        "Press the scroll wheel to open Stacka. One hand, no menu flash. Overrides middle-click's usual open-in-new-tab / autoscroll.":
            "Appuyez sur la molette pour ouvrir Stacka. D'une main, sans clignotement de menu. Remplace l'usage habituel du clic molette.",
        "Use a thumb Back/Forward button to open Stacka. Needs a mouse with side buttons.":
            "Utilisez un bouton latéral (précédent/suivant) pour ouvrir Stacka. Nécessite une souris à boutons latéraux.",
        "Hold Ctrl and right-click to open Stacka. Plain right-click stays normal. No menu flash.":
            "Maintenez Ctrl et faites un clic droit pour ouvrir Stacka. Le clic droit normal reste inchangé. Sans clignotement.",
        "A “Paste from Stacka” button appears beside the cursor on every right-click.":
            "Un bouton « Coller depuis Stacka » apparaît près du curseur à chaque clic droit.",
        "No mouse trigger — open Stacka only with your keyboard shortcut (see Shortcuts).":
            "Aucun déclencheur souris — ouvrez Stacka uniquement au clavier (voir Raccourcis).",
        # close behaviour
        "🖱  Click to close": "🖱  Cliquer pour fermer",
        "👆  Hover to close": "👆  Survoler pour fermer",
        "Click anywhere outside the app window and it closes.":
            "Cliquez hors de la fenêtre pour la fermer.",
        "Hover outside the app window automatically closes it.":
            "Survoler hors de la fenêtre la ferme automatiquement.",
        # shortcuts / history / profiles
        "Manage Shortcuts…": "Gérer les raccourcis…", "Launch Stacka:": "Ouvrir Stacka :",
        "History size limit:": "Limite de l'historique :", "items": "éléments",
        "Save Limit": "Enregistrer", "Clear All History": "Tout effacer",
        "Organise your clipboard into named workflow collections.":
            "Organisez votre presse-papiers en collections nommées.",
        # popup + context menus
        "Open link": "Ouvrir le lien", "Open": "Ouvrir",
        "Open containing folder": "Ouvrir le dossier",
        "Send to profile…": "Envoyer vers un profil…", "Send to profile": "Envoyer vers un profil",
        "➕  New profile…": "➕  Nouveau profil…",
        "Remove": "Retirer", "Pin": "Épingler", "Unpin": "Détacher",
        "Remove file": "Retirer le fichier", "Remove from list": "Retirer de la liste",
        "Clear selection": "Effacer la sélection", "Create a new profile": "Créer un profil",
        "Search clipboard…": "Rechercher…",
        "Profile:": "Profil :",
        "Clipboard history has been cleared.": "L'historique du presse-papiers a été effacé.",
        "selected": "sélectionné(s)",
        "No clipboard history yet.\nCopy something to get started!":
            "Aucun historique pour l'instant.\nCopiez quelque chose pour commencer !",
        "Support Stacka": "Soutenir Stacka", "Support": "Soutenir",
        "Support Stacka's development": "Soutenir le développement de Stacka",
    },
    "es": {
        "Auto-wipe": "Borrado auto",
        "Never": "Nunca",
        "Daily": "Diario",
        "Weekly": "Semanal",
        "Monthly": "Mensual",
        "Quarterly": "Trimestral",
        "Yearly": "Anual",
        "Next:": "Próximo:",
        "Done": "Listo",
        "History is kept until you clear it yourself.": "El historial se conserva hasta que lo borres.",
        "Clears every list automatically. Pinned items are kept.": "Borra todas las listas automáticamente. Los elementos fijados se conservan.",
        "Clear your entire clipboard history?": "¿Borrar todo el historial del portapapeles?",
        "This cannot be undone.": "Esta acción no se puede deshacer.",
        "Settings": "Ajustes", "Close": "Cerrar",
        "Clear History": "Borrar historial", "Quit Stacka": "Salir de Stacka",
        "Appearance": "Apariencia", "Sizing": "Tamaño", "Icon pack": "Paquete de iconos",
        "Popup trigger": "Activador", "Close behaviour": "Cierre",
        "Shortcuts": "Atajos", "History": "Historial", "Profiles": "Perfiles",
        "About Stacka": "Acerca de Stacka",
        "Theme:": "Tema:", "Dark": "Oscuro", "Light": "Claro",
        "Popup transparency:": "Transparencia:", "Row hover:": "Resalte:",
        "Indigo": "Índigo", "Gold": "Oro", "Emerald": "Esmeralda", "Rose": "Rosa",
        "Sky": "Cielo", "Violet": "Violeta", "Slate": "Pizarra",
        "10% steps · 100% = default": "pasos de 10 % · 100 % = predet.",
        "Row size": "Tamaño de fila", "Side list rows": "Filas del panel",
        "Font size": "Tamaño de letra",
        "🎨  Default Stacka": "🎨  Stacka predeterminado",
        "🏷  Labeled documents": "🏷  Documentos etiquetados",
        "Colourful modern icons — Office letter tiles, the Python logo, gears, and more.":
            "Iconos modernos y coloridos: fichas de Office, logo de Python, engranajes y más.",
        "Document-style icons with the file extension shown as a badge (PDF, DOCX, PNG…), one per extension.":
            "Iconos tipo documento con la extensión como insignia (PDF, DOCX, PNG…), uno por extensión.",
        "Pick up to two — e.g. overlay button + double right-click. “Hotkey only” can’t be combined.":
            "Elige hasta dos, p. ej. botón superpuesto + doble clic derecho. «Solo atajo» no se combina.",
        "🖱  Double right-click": "🖱  Doble clic derecho",
        "🖱  Middle-click": "🖱  Clic central",
        "⏪  Mouse side button": "⏪  Botón lateral",
        "⌨  Ctrl + right-click": "⌨  Ctrl + clic derecho",
        "🔘  Overlay button": "🔘  Botón superpuesto",
        "⌨  Hotkey only": "⌨  Solo atajo",
        "Right-click twice quickly to open Stacka at the cursor. One hand, never covers the app's own menu.":
            "Doble clic derecho rápido para abrir Stacka en el cursor. Con una mano, sin tapar el menú de la app.",
        "Press the scroll wheel to open Stacka. One hand, no menu flash. Overrides middle-click's usual open-in-new-tab / autoscroll.":
            "Pulsa la rueda para abrir Stacka. Con una mano, sin parpadeo de menú. Anula el uso normal del clic central.",
        "Use a thumb Back/Forward button to open Stacka. Needs a mouse with side buttons.":
            "Usa un botón lateral (atrás/adelante) para abrir Stacka. Necesita un ratón con botones laterales.",
        "Hold Ctrl and right-click to open Stacka. Plain right-click stays normal. No menu flash.":
            "Mantén Ctrl y haz clic derecho para abrir Stacka. El clic derecho normal no cambia. Sin parpadeo.",
        "A “Paste from Stacka” button appears beside the cursor on every right-click.":
            "Aparece un botón «Pegar desde Stacka» junto al cursor en cada clic derecho.",
        "No mouse trigger — open Stacka only with your keyboard shortcut (see Shortcuts).":
            "Sin activador de ratón: abre Stacka solo con el teclado (ver Atajos).",
        "🖱  Click to close": "🖱  Clic para cerrar",
        "👆  Hover to close": "👆  Pasar para cerrar",
        "Click anywhere outside the app window and it closes.":
            "Haz clic fuera de la ventana y se cierra.",
        "Hover outside the app window automatically closes it.":
            "Pasar el ratón fuera de la ventana la cierra automáticamente.",
        "Manage Shortcuts…": "Gestionar atajos…", "Launch Stacka:": "Abrir Stacka:",
        "History size limit:": "Límite del historial:", "items": "elementos",
        "Save Limit": "Guardar", "Clear All History": "Borrar todo",
        "Organise your clipboard into named workflow collections.":
            "Organiza tu portapapeles en colecciones con nombre.",
        # popup + context menus
        "Open link": "Abrir enlace", "Open": "Abrir",
        "Open containing folder": "Abrir carpeta",
        "Send to profile…": "Enviar a un perfil…", "Send to profile": "Enviar a un perfil",
        "➕  New profile…": "➕  Nuevo perfil…",
        "Remove": "Quitar", "Pin": "Fijar", "Unpin": "Desfijar",
        "Remove file": "Quitar archivo", "Remove from list": "Quitar de la lista",
        "Clear selection": "Limpiar selección", "Create a new profile": "Crear un perfil",
        "Search clipboard…": "Buscar…",
        "Profile:": "Perfil:",
        "Clipboard history has been cleared.": "Se ha borrado el historial del portapapeles.",
        "selected": "seleccionado(s)",
        "No clipboard history yet.\nCopy something to get started!":
            "Aún no hay historial.\n¡Copia algo para empezar!",
        "Support Stacka": "Apoyar Stacka", "Support": "Apoyar",
        "Support Stacka's development": "Apoya el desarrollo de Stacka",
    },
    "it": {
        "Auto-wipe": "Pulizia auto",
        "Never": "Mai",
        "Daily": "Giornaliera",
        "Weekly": "Settimanale",
        "Monthly": "Mensile",
        "Quarterly": "Trimestrale",
        "Yearly": "Annuale",
        "Next:": "Prossima:",
        "Done": "Fatto",
        "History is kept until you clear it yourself.": "La cronologia resta finché non la cancelli tu.",
        "Clears every list automatically. Pinned items are kept.": "Cancella automaticamente tutte le liste. Gli elementi fissati restano.",
        "Clear your entire clipboard history?": "Cancellare tutta la cronologia degli appunti?",
        "This cannot be undone.": "Questa azione è irreversibile.",
        "Settings": "Impostazioni", "Close": "Chiudi",
        "Clear History": "Cancella cronologia", "Quit Stacka": "Esci da Stacka",
        "Appearance": "Aspetto", "Sizing": "Dimensioni", "Icon pack": "Set di icone",
        "Popup trigger": "Attivazione", "Close behaviour": "Chiusura",
        "Shortcuts": "Scorciatoie", "History": "Cronologia", "Profiles": "Profili",
        "About Stacka": "Informazioni su Stacka",
        "Theme:": "Tema:", "Dark": "Scuro", "Light": "Chiaro",
        "Popup transparency:": "Trasparenza:", "Row hover:": "Evidenzia:",
        "Indigo": "Indaco", "Gold": "Oro", "Emerald": "Smeraldo", "Rose": "Rosa",
        "Sky": "Cielo", "Violet": "Viola", "Slate": "Ardesia",
        "10% steps · 100% = default": "passi del 10% · 100% = predefinito",
        "Row size": "Dimensione righe", "Side list rows": "Righe del pannello",
        "Font size": "Dimensione testo",
        "🎨  Default Stacka": "🎨  Stacka predefinito",
        "🏷  Labeled documents": "🏷  Documenti etichettati",
        "Colourful modern icons — Office letter tiles, the Python logo, gears, and more.":
            "Icone moderne e colorate: caselle Office, logo Python, ingranaggi e altro.",
        "Document-style icons with the file extension shown as a badge (PDF, DOCX, PNG…), one per extension.":
            "Icone in stile documento con l'estensione come badge (PDF, DOCX, PNG…), una per estensione.",
        "Pick up to two — e.g. overlay button + double right-click. “Hotkey only” can’t be combined.":
            "Scegline fino a due, es. pulsante sovrapposto + doppio clic destro. «Solo scorciatoia» non si combina.",
        "🖱  Double right-click": "🖱  Doppio clic destro",
        "🖱  Middle-click": "🖱  Clic centrale",
        "⏪  Mouse side button": "⏪  Pulsante laterale",
        "⌨  Ctrl + right-click": "⌨  Ctrl + clic destro",
        "🔘  Overlay button": "🔘  Pulsante sovrapposto",
        "⌨  Hotkey only": "⌨  Solo scorciatoia",
        "Right-click twice quickly to open Stacka at the cursor. One hand, never covers the app's own menu.":
            "Doppio clic destro rapido per aprire Stacka al cursore. Con una mano, senza coprire il menu dell'app.",
        "Press the scroll wheel to open Stacka. One hand, no menu flash. Overrides middle-click's usual open-in-new-tab / autoscroll.":
            "Premi la rotellina per aprire Stacka. Con una mano, senza lampeggio del menu. Sostituisce l'uso normale del clic centrale.",
        "Use a thumb Back/Forward button to open Stacka. Needs a mouse with side buttons.":
            "Usa un pulsante laterale (indietro/avanti) per aprire Stacka. Serve un mouse con pulsanti laterali.",
        "Hold Ctrl and right-click to open Stacka. Plain right-click stays normal. No menu flash.":
            "Tieni Ctrl e fai clic destro per aprire Stacka. Il clic destro normale resta invariato. Senza lampeggio.",
        "A “Paste from Stacka” button appears beside the cursor on every right-click.":
            "Un pulsante «Incolla da Stacka» appare vicino al cursore a ogni clic destro.",
        "No mouse trigger — open Stacka only with your keyboard shortcut (see Shortcuts).":
            "Nessun trigger del mouse: apri Stacka solo da tastiera (vedi Scorciatoie).",
        "🖱  Click to close": "🖱  Clic per chiudere",
        "👆  Hover to close": "👆  Passa per chiudere",
        "Click anywhere outside the app window and it closes.":
            "Fai clic fuori dalla finestra e si chiude.",
        "Hover outside the app window automatically closes it.":
            "Passare il mouse fuori dalla finestra la chiude in automatico.",
        "Manage Shortcuts…": "Gestisci scorciatoie…", "Launch Stacka:": "Apri Stacka:",
        "History size limit:": "Limite cronologia:", "items": "elementi",
        "Save Limit": "Salva", "Clear All History": "Cancella tutto",
        "Organise your clipboard into named workflow collections.":
            "Organizza gli appunti in raccolte con un nome.",
        # popup + context menus
        "Open link": "Apri link", "Open": "Apri",
        "Open containing folder": "Apri cartella",
        "Send to profile…": "Invia a un profilo…", "Send to profile": "Invia a un profilo",
        "➕  New profile…": "➕  Nuovo profilo…",
        "Remove": "Rimuovi", "Pin": "Fissa", "Unpin": "Sblocca",
        "Remove file": "Rimuovi file", "Remove from list": "Rimuovi dalla lista",
        "Clear selection": "Cancella selezione", "Create a new profile": "Crea un profilo",
        "Search clipboard…": "Cerca…",
        "Profile:": "Profilo:",
        "Clipboard history has been cleared.": "La cronologia degli appunti è stata cancellata.",
        "selected": "selezionati",
        "No clipboard history yet.\nCopy something to get started!":
            "Ancora nessuna cronologia.\nCopia qualcosa per iniziare!",
        "Support Stacka": "Sostieni Stacka", "Support": "Sostieni",
        "Support Stacka's development": "Sostieni lo sviluppo di Stacka",
    },
    "ru": {
        "Auto-wipe": "Автоочистка",
        "Never": "Никогда",
        "Daily": "Ежедневно",
        "Weekly": "Еженедельно",
        "Monthly": "Ежемесячно",
        "Quarterly": "Ежеквартально",
        "Yearly": "Ежегодно",
        "Next:": "Следующая:",
        "Done": "Готово",
        "History is kept until you clear it yourself.": "История хранится, пока вы не очистите её сами.",
        "Clears every list automatically. Pinned items are kept.": "Автоматически очищает все списки. Закреплённые элементы сохраняются.",
        "Clear your entire clipboard history?": "Очистить всю историю буфера обмена?",
        "This cannot be undone.": "Это действие нельзя отменить.",
        "Settings": "Настройки", "Close": "Закрыть",
        "Clear History": "Очистить историю", "Quit Stacka": "Выйти из Stacka",
        "Appearance": "Внешний вид", "Sizing": "Размер", "Icon pack": "Набор значков",
        "Popup trigger": "Способ вызова", "Close behaviour": "Закрытие",
        "Shortcuts": "Горячие клавиши", "History": "История", "Profiles": "Профили",
        "About Stacka": "О Stacka",
        "Theme:": "Тема:", "Dark": "Тёмная", "Light": "Светлая",
        "Popup transparency:": "Прозрачность:", "Row hover:": "Подсветка:",
        "Indigo": "Индиго", "Gold": "Золотой", "Emerald": "Изумруд", "Rose": "Розовый",
        "Sky": "Небесный", "Violet": "Фиолетовый", "Slate": "Сланец",
        "10% steps · 100% = default": "шаг 10% · 100% = по умолчанию",
        "Row size": "Размер строк", "Side list rows": "Строк в панели",
        "Font size": "Размер шрифта",
        "🎨  Default Stacka": "🎨  Stacka по умолчанию",
        "🏷  Labeled documents": "🏷  Документы с ярлыком",
        "Colourful modern icons — Office letter tiles, the Python logo, gears, and more.":
            "Современные цветные значки — плитки Office, логотип Python, шестерёнки и другое.",
        "Document-style icons with the file extension shown as a badge (PDF, DOCX, PNG…), one per extension.":
            "Значки-документы с расширением в виде метки (PDF, DOCX, PNG…), по одному на расширение.",
        "Pick up to two — e.g. overlay button + double right-click. “Hotkey only” can’t be combined.":
            "Выберите до двух — напр. кнопка-наложение + двойной правый клик. «Только клавиши» не сочетается.",
        "🖱  Double right-click": "🖱  Двойной правый клик",
        "🖱  Middle-click": "🖱  Клик колесом",
        "⏪  Mouse side button": "⏪  Боковая кнопка",
        "⌨  Ctrl + right-click": "⌨  Ctrl + правый клик",
        "🔘  Overlay button": "🔘  Кнопка-наложение",
        "⌨  Hotkey only": "⌨  Только клавиши",
        "Right-click twice quickly to open Stacka at the cursor. One hand, never covers the app's own menu.":
            "Быстрый двойной правый клик открывает Stacka у курсора. Одной рукой, не перекрывая меню приложения.",
        "Press the scroll wheel to open Stacka. One hand, no menu flash. Overrides middle-click's usual open-in-new-tab / autoscroll.":
            "Нажмите колесо, чтобы открыть Stacka. Одной рукой, без мигания меню. Заменяет обычное действие средней кнопки.",
        "Use a thumb Back/Forward button to open Stacka. Needs a mouse with side buttons.":
            "Используйте боковую кнопку (назад/вперёд), чтобы открыть Stacka. Нужна мышь с боковыми кнопками.",
        "Hold Ctrl and right-click to open Stacka. Plain right-click stays normal. No menu flash.":
            "Удерживайте Ctrl и щёлкните правой кнопкой. Обычный правый клик не меняется. Без мигания.",
        "A “Paste from Stacka” button appears beside the cursor on every right-click.":
            "Кнопка «Вставить из Stacka» появляется у курсора при каждом правом клике.",
        "No mouse trigger — open Stacka only with your keyboard shortcut (see Shortcuts).":
            "Без мышиного триггера — открывайте Stacka только с клавиатуры (см. Горячие клавиши).",
        "🖱  Click to close": "🖱  Клик для закрытия",
        "👆  Hover to close": "👆  Наведение закрывает",
        "Click anywhere outside the app window and it closes.":
            "Щёлкните вне окна — и оно закроется.",
        "Hover outside the app window automatically closes it.":
            "Наведение вне окна закрывает его автоматически.",
        "Manage Shortcuts…": "Настроить клавиши…", "Launch Stacka:": "Открыть Stacka:",
        "History size limit:": "Лимит истории:", "items": "элем.",
        "Save Limit": "Сохранить", "Clear All History": "Очистить всё",
        "Organise your clipboard into named workflow collections.":
            "Упорядочьте буфер обмена в именованные коллекции.",
        # popup + context menus
        "Open link": "Открыть ссылку", "Open": "Открыть",
        "Open containing folder": "Открыть папку",
        "Send to profile…": "Отправить в профиль…", "Send to profile": "Отправить в профиль",
        "➕  New profile…": "➕  Новый профиль…",
        "Remove": "Убрать", "Pin": "Закрепить", "Unpin": "Открепить",
        "Remove file": "Убрать файл", "Remove from list": "Убрать из списка",
        "Clear selection": "Снять выделение", "Create a new profile": "Создать профиль",
        "Search clipboard…": "Поиск…",
        "Profile:": "Профиль:",
        "Clipboard history has been cleared.": "История буфера обмена очищена.",
        "selected": "выбрано",
        "No clipboard history yet.\nCopy something to get started!":
            "Истории пока нет.\nСкопируйте что-нибудь, чтобы начать!",
        "Support Stacka": "Поддержать Stacka", "Support": "Поддержать",
        "Support Stacka's development": "Поддержать разработку Stacka",
    },
    "zh": {
        "Auto-wipe": "自动清除",
        "Never": "从不",
        "Daily": "每天",
        "Weekly": "每周",
        "Monthly": "每月",
        "Quarterly": "每季度",
        "Yearly": "每年",
        "Next:": "下次：",
        "Done": "完成",
        "History is kept until you clear it yourself.": "历史将一直保留，直到您手动清除。",
        "Clears every list automatically. Pinned items are kept.": "自动清空所有列表。置顶项目会保留。",
        "Clear your entire clipboard history?": "清除全部剪贴板历史？",
        "This cannot be undone.": "此操作无法撤销。",
        "Settings": "设置", "Close": "关闭",
        "Clear History": "清除历史", "Quit Stacka": "退出 Stacka",
        "Appearance": "外观", "Sizing": "尺寸", "Icon pack": "图标包",
        "Popup trigger": "弹出触发", "Close behaviour": "关闭方式",
        "Shortcuts": "快捷键", "History": "历史", "Profiles": "配置文件",
        "About Stacka": "关于 Stacka",
        "Theme:": "主题：", "Dark": "深色", "Light": "浅色",
        "Popup transparency:": "透明度：", "Row hover:": "悬停色：",
        "Indigo": "靛蓝", "Gold": "金色", "Emerald": "翠绿", "Rose": "玫红",
        "Sky": "天蓝", "Violet": "紫罗兰", "Slate": "石板灰",
        "10% steps · 100% = default": "10% 步进 · 100% = 默认",
        "Row size": "行大小", "Side list rows": "侧栏行数",
        "Font size": "字体大小",
        "🎨  Default Stacka": "🎨  Stacka 默认",
        "🏷  Labeled documents": "🏷  带标签文档",
        "Colourful modern icons — Office letter tiles, the Python logo, gears, and more.":
            "彩色现代图标——Office 字母块、Python 徽标、齿轮等。",
        "Document-style icons with the file extension shown as a badge (PDF, DOCX, PNG…), one per extension.":
            "文档式图标，扩展名以徽章显示（PDF、DOCX、PNG…），每种扩展名一个。",
        "Pick up to two — e.g. overlay button + double right-click. “Hotkey only” can’t be combined.":
            "最多选两种，如浮层按钮 + 双击右键。“仅快捷键”不可组合。",
        "🖱  Double right-click": "🖱  双击右键",
        "🖱  Middle-click": "🖱  中键点击",
        "⏪  Mouse side button": "⏪  鼠标侧键",
        "⌨  Ctrl + right-click": "⌨  Ctrl + 右键",
        "🔘  Overlay button": "🔘  浮层按钮",
        "⌨  Hotkey only": "⌨  仅快捷键",
        "Right-click twice quickly to open Stacka at the cursor. One hand, never covers the app's own menu.":
            "快速双击右键，在光标处打开 Stacka。单手操作，不遮挡应用自身菜单。",
        "Press the scroll wheel to open Stacka. One hand, no menu flash. Overrides middle-click's usual open-in-new-tab / autoscroll.":
            "按下滚轮打开 Stacka。单手操作，菜单不闪烁。会覆盖中键的常规用途。",
        "Use a thumb Back/Forward button to open Stacka. Needs a mouse with side buttons.":
            "使用拇指侧键（后退/前进）打开 Stacka。需要带侧键的鼠标。",
        "Hold Ctrl and right-click to open Stacka. Plain right-click stays normal. No menu flash.":
            "按住 Ctrl 再右键打开 Stacka。普通右键不变，菜单不闪烁。",
        "A “Paste from Stacka” button appears beside the cursor on every right-click.":
            "每次右键时，光标旁会出现“从 Stacka 粘贴”按钮。",
        "No mouse trigger — open Stacka only with your keyboard shortcut (see Shortcuts).":
            "无鼠标触发——仅用键盘快捷键打开 Stacka（见快捷键）。",
        "🖱  Click to close": "🖱  点击关闭",
        "👆  Hover to close": "👆  悬停关闭",
        "Click anywhere outside the app window and it closes.":
            "在窗口外点击任意处即可关闭。",
        "Hover outside the app window automatically closes it.":
            "将鼠标移出窗口会自动关闭。",
        "Manage Shortcuts…": "管理快捷键…", "Launch Stacka:": "打开 Stacka：",
        "History size limit:": "历史上限：", "items": "项",
        "Save Limit": "保存", "Clear All History": "全部清除",
        "Organise your clipboard into named workflow collections.":
            "把剪贴板整理成命名的集合。",
        # popup + context menus
        "Open link": "打开链接", "Open": "打开",
        "Open containing folder": "打开所在文件夹",
        "Send to profile…": "发送到配置文件…", "Send to profile": "发送到配置文件",
        "➕  New profile…": "➕  新建配置文件…",
        "Remove": "移除", "Pin": "置顶", "Unpin": "取消置顶",
        "Remove file": "移除文件", "Remove from list": "从列表移除",
        "Clear selection": "清除选择", "Create a new profile": "新建配置文件",
        "Search clipboard…": "搜索…",
        "Profile:": "配置文件：",
        "Clipboard history has been cleared.": "剪贴板历史已清除。",
        "selected": "已选",
        "No clipboard history yet.\nCopy something to get started!":
            "还没有剪贴板历史。\n复制一些内容开始使用！",
        "Support Stacka": "支持 Stacka", "Support": "支持",
        "Support Stacka's development": "支持 Stacka 的开发",
    },
    "ko": {
        "Auto-wipe": "자동 삭제",
        "Never": "안 함",
        "Daily": "매일",
        "Weekly": "매주",
        "Monthly": "매월",
        "Quarterly": "분기별",
        "Yearly": "매년",
        "Next:": "다음:",
        "Done": "완료",
        "History is kept until you clear it yourself.": "직접 지울 때까지 기록이 유지됩니다.",
        "Clears every list automatically. Pinned items are kept.": "모든 목록을 자동으로 비웁니다. 고정된 항목은 유지됩니다.",
        "Clear your entire clipboard history?": "클립보드 기록을 모두 지우시겠습니까?",
        "This cannot be undone.": "이 작업은 되돌릴 수 없습니다.",
        "Settings": "설정", "Close": "닫기",
        "Clear History": "기록 지우기", "Quit Stacka": "Stacka 종료",
        "Appearance": "모양", "Sizing": "크기", "Icon pack": "아이콘 팩",
        "Popup trigger": "팝업 트리거", "Close behaviour": "닫기 동작",
        "Shortcuts": "단축키", "History": "기록", "Profiles": "프로필",
        "About Stacka": "Stacka 정보",
        "Theme:": "테마:", "Dark": "다크", "Light": "라이트",
        "Popup transparency:": "투명도:", "Row hover:": "호버 색:",
        "Indigo": "인디고", "Gold": "골드", "Emerald": "에메랄드", "Rose": "로즈",
        "Sky": "스카이", "Violet": "바이올렛", "Slate": "슬레이트",
        "10% steps · 100% = default": "10% 단위 · 100% = 기본",
        "Row size": "행 크기", "Side list rows": "측면 목록 행",
        "Font size": "글자 크기",
        "🎨  Default Stacka": "🎨  Stacka 기본",
        "🏷  Labeled documents": "🏷  라벨 문서",
        "Colourful modern icons — Office letter tiles, the Python logo, gears, and more.":
            "다채로운 현대적 아이콘 — Office 글자 타일, Python 로고, 기어 등.",
        "Document-style icons with the file extension shown as a badge (PDF, DOCX, PNG…), one per extension.":
            "확장자를 배지로 표시하는 문서형 아이콘(PDF, DOCX, PNG…), 확장자마다 하나씩.",
        "Pick up to two — e.g. overlay button + double right-click. “Hotkey only” can’t be combined.":
            "최대 두 개 선택 — 예: 오버레이 버튼 + 더블 우클릭. ‘단축키 전용’은 조합 불가.",
        "🖱  Double right-click": "🖱  더블 우클릭",
        "🖱  Middle-click": "🖱  가운데 클릭",
        "⏪  Mouse side button": "⏪  마우스 측면 버튼",
        "⌨  Ctrl + right-click": "⌨  Ctrl + 우클릭",
        "🔘  Overlay button": "🔘  오버레이 버튼",
        "⌨  Hotkey only": "⌨  단축키 전용",
        "Right-click twice quickly to open Stacka at the cursor. One hand, never covers the app's own menu.":
            "우클릭을 빠르게 두 번 하면 커서 위치에 Stacka이 열립니다. 한 손으로, 앱 메뉴를 가리지 않습니다.",
        "Press the scroll wheel to open Stacka. One hand, no menu flash. Overrides middle-click's usual open-in-new-tab / autoscroll.":
            "휠을 누르면 Stacka이 열립니다. 한 손으로, 메뉴 깜빡임 없음. 가운데 클릭의 기본 동작을 대체합니다.",
        "Use a thumb Back/Forward button to open Stacka. Needs a mouse with side buttons.":
            "엄지 측면 버튼(뒤로/앞으로)으로 Stacka을 엽니다. 측면 버튼이 있는 마우스가 필요합니다.",
        "Hold Ctrl and right-click to open Stacka. Plain right-click stays normal. No menu flash.":
            "Ctrl을 누른 채 우클릭하면 Stacka이 열립니다. 일반 우클릭은 그대로, 깜빡임 없음.",
        "A “Paste from Stacka” button appears beside the cursor on every right-click.":
            "우클릭할 때마다 커서 옆에 ‘Stacka에서 붙여넣기’ 버튼이 나타납니다.",
        "No mouse trigger — open Stacka only with your keyboard shortcut (see Shortcuts).":
            "마우스 트리거 없음 — 키보드 단축키로만 Stacka을 엽니다(단축키 참고).",
        "🖱  Click to close": "🖱  클릭하여 닫기",
        "👆  Hover to close": "👆  호버로 닫기",
        "Click anywhere outside the app window and it closes.":
            "창 밖 아무 곳이나 클릭하면 닫힙니다.",
        "Hover outside the app window automatically closes it.":
            "창 밖으로 마우스를 옮기면 자동으로 닫힙니다.",
        "Manage Shortcuts…": "단축키 관리…", "Launch Stacka:": "Stacka 열기:",
        "History size limit:": "기록 제한:", "items": "개",
        "Save Limit": "저장", "Clear All History": "모두 지우기",
        "Organise your clipboard into named workflow collections.":
            "클립보드를 이름 있는 컬렉션으로 정리하세요.",
        # popup + context menus
        "Open link": "링크 열기", "Open": "열기",
        "Open containing folder": "폴더 열기",
        "Send to profile…": "프로필로 보내기…", "Send to profile": "프로필로 보내기",
        "➕  New profile…": "➕  새 프로필…",
        "Remove": "제거", "Pin": "고정", "Unpin": "고정 해제",
        "Remove file": "파일 제거", "Remove from list": "목록에서 제거",
        "Clear selection": "선택 해제", "Create a new profile": "새 프로필 만들기",
        "Search clipboard…": "검색…",
        "Profile:": "프로필:",
        "Clipboard history has been cleared.": "클립보드 기록이 지워졌습니다.",
        "selected": "선택됨",
        "No clipboard history yet.\nCopy something to get started!":
            "아직 클립보드 기록이 없습니다.\n무언가를 복사해 시작하세요!",
        "Support Stacka": "Stacka 후원", "Support": "후원",
        "Support Stacka's development": "Stacka 개발 후원",
    },
}
