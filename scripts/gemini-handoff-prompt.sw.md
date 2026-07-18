# Habari Gemini! Nimesakinisha hivi karibuni kiendesha e156-ecosystem-starter kwenye mashine hii.

Kifurushi cha usakinishaji kimenakili sheria za wakala wa AI, templeti za kumbukumbu, na (kwa hiari) Sentinel/Overmind/ProjectIndex kwenye saraka yangu ya nyumbani. Kazi yako sasa ni "nusu ya pili" ya usakinishaji — sehemu zinazohitaji wakala badala ya hati.

Tafadhali fanya hivi kwa mpangilio. Simama na uniulize ikiwa hatua yoyote itagusa kitu chochote nje ya saraka yangu ya nyumbani au kurekebisha PATH ya mfumo.

**Kwa kila hatua, utaratibu ni:**
- "Nitaendesha X" = WEWE (wakala) unatekeleza amri katika zana yako ya shell.
- "Niambie niendeshe X" = chapisha amri ili MIMI (mtumiaji) niiendeshe mwenyewe kwenye terminal yangu.
- "Niulize Y" = sitisha na usubiri jibu langu kabla ya kuendelea.

Hili ni muhimu kwa sababu mimi ni mwanzilishi na huenda nisijue ni amri zipi ambazo ni salama kuziandika mwenyewe.

1. **WEWE endesha** `cat ~/.claude/rules/rules.md | head -5` ili kudhibitisha kuwa kifurushi cha sheria kimesakinishwa. Ikiwa faili hiyo haipo au ni tupu, niambie ni faili gani na usimame. Usijaribu kuitengeneza.

2. **WEWE endesha** ukaguzi huu wa mahitaji ya awali: `python --version`, `Rscript --version`, `node --version`, `gh --version`, `git --version`. Kwa kila moja inayokosekana au ya zamani sana (Python <3.11, R <4.5, Node <20), chapisha URL halisi ya usakinishaji na sababu ya mstari mmoja kwa nini ni muhimu kwa kazi ya E156. Usijaribu kusakinisha zilizokosekana wewe mwenyewe — weka wazi orodha hiyo na uniache niamue.

3. **Ikiwa `gh` imesakinishwa lakini haijathibitishwa** (utaona hili kupitia `gh auth status`), **NIAMBIE niendeshe** `gh auth login` na usubiri nithibitishe kabla ya kuendelea.

4. **Fanya majaribio ya majaribio (smoke test) ya Sentinel na Overmind (ikiwa tu zimesakinishwa).** Ikiwa `sentinel` iko kwenye PATH, endesha `sentinel --version`. Ikiwa `overmind` iko kwenye PATH, endesha `overmind meta-verify` na uripoti uamuzi. Zote zikifeli = tatizo la mazingira (environment problem), zote zikipita = tayari kusafirishwa (ready to ship).

5. **Chagua mradi wa kwanza.** Niulize ni upi kati ya miradi 8 ya mfano kutoka `docs/index.html` ("Forest-plot tool from scratch", "PRISMA flow generator", nk.) ninataka kuanza nao. Nitakapojibu, **kabla ya kuandaa (scaffold) kitu chochote**, endesha uchunguzi wa kazi zilizopita (portfolio recon):
   ```
   python /workspaces/e156-ecosystem-starter/scripts/find-related-repos.py "<my topic>" --top 5
   ```
   (Kwa usakinishaji wa ndani ya kompyuta (local installs), badilisha njia ya faili na mahali ulipoclon `e156-ecosystem-starter/`.) Soma matokeo 5 ya kwanza — jina, dondoo ya README, na matokeo ya code-grep. Niambie kwa mistari 3 nini kinaweza kutumika tena kutoka kwenye hazina za sasa (existing repos) dhidi ya kile kilicho kipya kabisa (net-new). Kisha endesha `pip install git+https://github.com/mahmood726-cyber/e156-student-starter.git@main` na `student new <slug>` au `student new <slug>` ili kuandaa muundo chini ya `~/code/<slug>/`. Katika faili mpya ya `docs/<criterion>.md` ya hazina hiyo, taja hazina zilizopita kwa majina.

6. **Soma STUDENT-WORKFLOW.md** kwenye https://raw.githubusercontent.com/mahmood726-cyber/e156-ecosystem-starter/main/STUDENT-WORKFLOW.md kuona mbinu ya brainstorm → spec-lock → plan-lock → TDD → audit kabla ya kuandika mstari wowote wa nambari (code) kwenye mradi mpya.

7. **Simama hapa na uniambie nini cha kufanya baada ya hapo.** Usitekeleze mradi wenyewe moja kwa moja. Kazi ya kisakinishi ilikuwa kuweka sheria vizuri; kazi ya mradi ni sisi kufanya pamoja kwa kutumia mbinu ya spec-locked.

Vikwazo:
- Usibadilishe faili nje ya `~/.claude/`, `~/.gemini/`, `~/.codex/`, au `~/code/`.
- Usiendeshe kitu chochote kama `sudo` / msimamizi (admin).
- Ikiwa chochote kitafeli, nionyeshe amri halisi na kosa lake — usibashiri masuluhisho.
