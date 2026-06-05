# Bonjour Gemini ! Je viens de lancer l'installateur e156-ecosystem-starter sur cette machine.

L'installateur a copié les règles d'agent IA, les modèles de mémoire, et (en option)
Sentinel/Overmind/ProjectIndex dans mon dossier personnel. Ton travail maintenant est
la « seconde moitié » de l'installation — les parties qui nécessitent un agent, pas un script.

Fais ces étapes dans l'ordre. Arrête-toi et demande-moi si une étape devait toucher
quelque chose en dehors de mon dossier personnel ou modifier le PATH système.

1. **Vérification rapide de l'installation.** Lis `~/.claude/rules/rules.md` et confirme
   que les quatre fichiers de règles sont présents (`rules.md`, `e156.md`,
   `advanced-stats.md`, `lessons.md`). Si l'un d'eux manque, dis-moi lesquels et arrête-toi.

2. **Diagnostique les prérequis manquants et dis-moi quoi installer.** Exécute
   `python --version`, `Rscript --version`, `node --version`, `gh --version`,
   `git --version`. Pour chacun absent ou trop ancien (Python <3.11, R <4.5, Node <20),
   affiche l'URL d'installation exacte et une ligne expliquant pourquoi c'est utile pour
   le travail E156. Ne les installe pas toi-même — laisse-moi voir la liste et décider.

3. **Si `gh` est installé mais non authentifié**, dis-moi de lancer `gh auth login`
   et attends. Ne continue pas avant ma confirmation.

4. **Test rapide de Sentinel et Overmind (s'ils sont installés).** Si `sentinel` est sur
   le PATH, exécute `sentinel --version`. Si `overmind` est sur le PATH, exécute
   `overmind meta-verify` et rapporte le verdict. Les deux qui échouent = problème
   d'environnement, les deux qui passent = prêt à livrer.

5. **Choisir un premier projet.** Demande-moi lequel des 8 projets exemples de
   `docs/index.html` (« Outil de forest-plot », « Générateur de diagramme PRISMA »,
   etc.) je veux commencer. Quand je réponds, **avant de scaffolder quoi que ce soit**,
   exécute la reconnaissance de portfolio :
   ```
   python /workspaces/e156-ecosystem-starter/scripts/find-related-repos.py "<mon sujet>" --top 5
   ```
   (Pour les installations locales, remplace le chemin par celui où tu as cloné
   `e156-ecosystem-starter/`.) Lis les 5 meilleurs résultats — nom, extrait du README,
   résultats de grep de code. Dis-moi en 3 lignes ce qui est réutilisable depuis les
   dépôts existants vs ce qui est vraiment nouveau. **Cherche aussi les briques
   réutilisables** pour copier au lieu de régénérer — copier une primitive existante
   coûte zéro token, la régénérer en coûte des milliers :
   ```
   python /workspaces/e156-ecosystem-starter/scripts/reuse.py find "<ce dont tu as besoin>"
   ```
   (p. ex. « forest plot », « aact loader »). L'outil renvoie la fonction du kit et le
   fichier exacts à copier. Puis exécute
   `pip install git+https://github.com/mahmood726-cyber/e156-student-starter.git@main`
   et `student new <slug>` pour scaffolder sous `~/code/<slug>/`. Dans le `docs/<criterion>.md`
   du nouveau dépôt, cite les dépôts antérieurs par nom.

6. **Lis STUDENT-WORKFLOW.md** à
   https://raw.githubusercontent.com/mahmood726-cyber/e156-ecosystem-starter/main/STUDENT-WORKFLOW.md
   pour comprendre la méthode brainstorm → spec-lock → plan-lock → TDD → audit
   avant d'écrire une seule ligne de code dans le nouveau projet.

7. **Arrête-toi ici et dis-moi quoi faire ensuite.** N'auto-implémente pas le projet.
   Le rôle de l'installateur était de mettre les règles en place ; le rôle du projet est
   pour nous de le faire ensemble en utilisant la méthode spec-locked.

Contraintes :
- Ne modifie pas de fichiers en dehors de `~/.claude/`, `~/.gemini/`, `~/.codex/`, ou `~/code/`.
- N'exécute rien en `sudo` / admin.
- Si quelque chose échoue, montre-moi la commande exacte et l'erreur — ne devine pas les correctifs.
