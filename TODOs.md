# Mafia Bot TODO List

This document outlines the necessary tasks to complete the Mafia Bot, focusing on implementing the core game loop, action resolution, and win conditions.

## I. Core Game Loop & Phase Management (`src/handlers/game_management/phase_manager.py`, `main.py`)

-   [x] **Implement Game State Machine:** Design and implement a robust state machine to manage the game flow (e.g., `PRE_GAME` -> `NIGHT` -> `NIGHT_RESOLVE` -> `DAY_ANNOUNCE` -> `DAY_DISCUSS` -> `VOTING` -> `VOTE_RESOLVE` -> `CHECK_WIN` -> `NIGHT`...).
-   [x] **Automate Phase Transitions:** Modify `main.py` or create a dedicated game loop manager that automatically calls the correct phase functions based on the current game state and completion of previous phases.
    -   [x] Trigger `resolve_night_actions` after a set time or when all actions are submitted.
    -   [x] Trigger `start_day_phase` after night resolution.
    -   [x] Trigger `prompt_voting_permissions` (or directly start voting if permissions are standard) after day discussion/actions.
    *   [x] Trigger `process_voting_results` after voting concludes.
    *   [x] Trigger `apply_voting_outcome` (New Function) after results are processed.
    *   [x] Trigger `check_win_condition` (New Function) after night and day resolutions.
    *   [x] Trigger `start_night_phase` if the game continues.
-   [x] **Implement Phase Timers (Optional but Recommended):** Add configurable timers for night actions, day discussion, and voting phases using `context.job_queue`.
-   [x] **Update Game Phase in DB:** Ensure `Games.current_phase` is consistently updated during transitions.

## II. Night Action Resolution (`src/handlers/game_management/phase_manager.py`)

-   [x] **Refactor `resolve_night_actions`:** Overhaul the function for robust action resolution.
-   [x] **Fetch All Night Actions:** Retrieve all recorded actions for the current night from the `Actions` table for the given `game_id`.
-   [x] **Implement Action Priority:** Sort and process actions based on the `priority` field defined in `data/roles.json`. Higher priority actions resolve first.
-   [x] **Implement Core Action Effects:**
    -   [x] **Mafia Kill (`God F`):** Aggregate Mafia kill attempts, handle Godfather's final decision. Implement kill transfer logic if Godfather is removed (`Joker`, `DoctorLec`, `Natasha`).
    -   [x] **Doctor Save:** Track who the Doctor chose to save. Apply save against Mafia kill attempts *before* determining death. Handle self-save.
    -   [x] **Detective Investigation (`Kar Agah`):** Determine target's faction (handle `God F`, `DoubleFace`, `MaskedFigure` exceptions/interactions). Store result to be sent privately *after* night resolution. Handle interaction with `Joker`.
    -   [x] **Sniper Shot (`Tak Tir`):** Determine target. Check if target is Villager faction. Apply kill if Mafia/Independent. If Villager, mark *both* Sniper and target for elimination. Apply kill based on priority relative to saves/kills. Handle interaction with `DoctorLec`, `Commander`.
    -   [x] **Cowboy Shoot:** Mark target and Cowboy for elimination. Apply based on priority.
    -   [x] **Gunsmith (`Tof Dar`) Distribute Guns:** Implement logic to track who receives real/fake guns (requires adding columns/tables to DB or using `context.bot_data`/persistent storage). *This is complex and might be deferred.*
    -   [ ] **Other Roles:** Implement effects for all other roles with night actions, passive abilities, or triggers as detailed in Section X.
-   [x] **Consolidate Night Outcomes:** Determine the final list of players eliminated during the night based on all resolved actions (kills, saves, suicides, immunities, role interactions, etc.).
-   [x] **Update Player Status:** Update the `eliminated` status in the `Roles` table for players who died.
-   [x] **Announce Night Results:** Send a public message to the game chat (or all players individually) announcing who was eliminated during the night (without revealing causes unless game rules/roles specify, e.g., `Efsha Gar`, `Revealer`).
-   [x] **Send Private Results:** Send private results (e.g., Detective's findings, Spy's info, Hacker's result, Inquisitor's result) to the relevant players.
-   [x] **Clear Night Actions:** Delete processed actions from the `Actions` table for the completed night phase.

## III. Day Phase & Voting Integration (`src/handlers/game_management/voting.py`, `src/handlers/game_management/phase_manager.py`)

-   [ ] **Implement `resolve_day_actions`:** If any non-voting day actions are defined (e.g., Gun usage from `Gunsmith`/`MunitionsExpert`, `Jigsaw`'s Gas Chamber, `RussianRoulette` trigger), implement their resolution logic here.
-   [x] **Implement Voting Outcome Application:** Create a new function `apply_voting_outcome(game_id, context)` called after `process_voting_results`.
    -   [x] Determine the player(s) with the most votes based on `vote_counts` from `process_voting_results`.
    -   [x] Handle ties (e.g., no elimination, random tie-break, revote - define game rules).
    -   [x] Handle vote modification/overrides (e.g., `Ghazi`, `Sacrifice`, `WiseMan`, `Syndicate`).
    -   [x] Update the `eliminated` status in the `Roles` table for the player(s) voted out.
    -   [x] Announce the outcome publicly (who was eliminated by vote). Handle role reveal suppression/trigger (`Executioner`, `Efsha Gar`, `Revealer`, `PoliceChief`, `Terrorist`).
-   [x] **Integrate Voting Trigger:** Ensure the game loop automatically triggers the voting phase (`prompt_voting_permissions` or similar) after the day discussion period.
-   [ ] **Handle Day Triggers:** Implement logic for effects triggered by day events (e.g., `Terrorist` explosive exit, `PoliceChief` last shot, `Exposer` reveal, `Enchanter`/`LadyVoodoo` word curse check, `Dynamite` bomb resolution, `Jigsaw` gas chamber).

## IV. Win Condition Logic (`src/handlers/game_management/phase_manager.py` or new module)

-   [x] **Create `check_win_condition(game_id)` function:** This function should be called after night resolution and after voting resolution.
-   [x] **Fetch Current Game State:** Get counts of active players per faction (Mafia, Villager, Independents, etc.).
-   [x] **Implement Win Condition Checks:**
    -   [x] Mafia wins if `num_mafia >= num_villagers` (or other town-aligned roles).
    -   [x] Villagers win if `num_mafia == 0` and no hostile Independents remain.
    -   [ ] Implement checks for Independent roles' win conditions (`Zodiac`, `Jigsaw`, `JackSparrow`, `SherlockHolmes`, `Carrier`, `Werewolf`, `Syndicate`, `Killer`, `Corona`, `Unknown`, `ThousandFace`).
    -   [ ] Implement check for `Nanva` (Baker) death timer.
-   [x] **End Game:** If a win condition is met:
    -   [x] Update the game state in the `Games` table (e.g., set `started = 2` or add a `winner` column).
    -   [x] Announce the game end and the winning faction/players.
    -   [x] Optionally reveal all remaining roles.
    -   [x] Clean up any persistent game data (locks, timers, etc.).

## V. State Management & Persistence

-   [x] **Persist Voting State:** Refactor `src/handlers/game_management/voting.py`. Store `game_voting_data` (votes, voters, permissions, anonymous status, summary message ID) in the database instead of memory. This could involve new tables (e.g., `VotingSessions`, `Votes`) or adding JSON columns to `Games`.
-   [x] **Review `context.user_data`:** Audit the use of `user_data` to ensure state is cleared appropriately (e.g., `action`, `current_page`, `game_id` when leaving/finishing a game).
-   [ ] **Persist Action Data:** The `Actions` table already persists chosen actions, which is good. Ensure it's cleared correctly after each phase resolution.
-   [ ] **Persist Role State:** Add mechanisms (e.g., JSON column in `Roles` table, separate `RoleState` table) to track uses left (`Efsha Gar`, `Ghazi`, `Afyun`, `MaskedFigure`, `MafiaSpecialist`, `Butcher`, `StrongMan`, `NamelessMafia`, `PoisonMaker`, `AdamSnowman`, `Gambler`, `Elite`, `Wizard`, `Bomber`, `Physician`, `NightWatch`, `Swordsman`, `MunitionsExpert`, `WiseMan`), cooldowns (`Werewolf`), statuses (immunity used `Ruyin tan`, linked players `Link`/`Hunter`/`Spider`, cursed words `Enchanter`/`LadyVoodoo`, bomb target `Dynamite`, gun holder `Gunsmith`/`Tof Dar`/`RussianRoulette`/`Avenger`/`MunitionsExpert`/`Swordsman`, infection status `Carrier`/`Corona`, mimic target `Doppelganger`, etc.).

## VI. Refactoring & Code Quality

-   [ ] **Refactor `button_handler.py`:**
    -   [ ] Break `handle_button` into smaller, more focused functions based on callback data prefixes (e.g., `handle_role_button`, `handle_vote_button`, `handle_moderator_button`).
    -   [ ] Consider using a dictionary mapping prefixes to handler functions instead of a long `if/elif` chain.
-   [ ] **Improve Database Migrations:** Use a more robust migration system (e.g., basic version tracking in a separate table) instead of relying solely on `PRAGMA table_info` checks on every startup.
-   [ ] **Consistent Transaction Usage:** Review all database operations that modify data across multiple steps (e.g., action resolution, role assignment, voting outcome) and ensure they are wrapped in transactions (`BEGIN`, `COMMIT`, `ROLLBACK`).
-   [ ] **Improve Inline Comments:** Add more comments explaining complex logic, especially in `phase_manager.py`, `voting.py`, `button_handler.py`, and role-specific implementations.

## VII. Error Handling & User Experience

-   [x] **Granular Error Handling:** Add more specific `try...except` blocks around potentially failing operations (DB writes, API calls, sending messages) within handlers and provide user-friendly feedback.
-   [x] **Clearer Phase Transitions:** Provide explicit messages to users indicating the start and end of each phase (Night, Day, Voting).
-   [ ] **Handle Bot Restarts:** Implement logic to gracefully handle bot restarts, potentially resuming games if state is persisted correctly (Advanced).
-   [ ] **Action Feedback:** Provide confirmation messages when users submit actions and clear feedback if an action fails (e.g., target invalid, out of uses).


## X. Role-Specific Abilities (Detailed Implementation)

This section details the implementation required for roles beyond the basic ones covered in Section II. Logic should primarily reside in `resolve_night_actions`, `resolve_day_actions`, `apply_voting_outcome`, or dedicated trigger handlers, interacting with persisted role state (See Section V).

**Villager Roles:**

-   [x] **`Ruyin tan` (Bulletproof):** Implement one-time night kill immunity. Check status before applying night kills. Persist immunity used status.
-   [ ] **`Jasoos` (Spy):** Implement logic (likely in `start_night_phase` or special first-night handler) to send the list of Mafia members to the Spy on Night 1 only.
-   [ ] **`Keshish` (Priest - Unsilence):** Implement night action to remove 'silenced' status. Needs interaction with `Natasha`. Implement day-death trigger to reveal one player's role.
-   [ ] **`Nanva` (Baker):** Implement death trigger: start a game-level countdown (e.g., 5 days) upon Baker's death. Check countdown in `check_win_condition` or phase transition; if reaches zero, Villagers lose (or game ends based on rules).
-   [ ] **`Bisim chi` (Radio Operator):** Implement night action. Check if both targets are Villagers; if so, send private messages to both targets revealing each other.
-   [ ] **`Hacker`:** Implement Night 1 action. Check factions of targets. Trigger appropriate public announcement ("dangerous" / "not dangerous") during `start_day_phase`.
-   [ ] **`Efsha Gar` (Revealer):** Implement night action with use tracking (2 uses). Persist targets. Implement logic during player elimination announcement to check if the eliminated player was targeted by `Efsha Gar` and reveal their role if so.
-   [ ] **`Afyun` (Opium Dealer):** Implement night action with use tracking (1 use). Action should block *all* Mafia night actions for that night and eliminate the `Afyun` player during night resolution.
-   [ ] **`Gor Kan` (Gravedigger):** Implement night action. Set a flag to trigger a public announcement of all eliminated players' roles during the *next* `start_day_phase`.
-   [ ] **`Ghazi` (Judge):** Implement night action with use tracking (1 use). This action likely needs to trigger during `apply_voting_outcome` to allow overriding the vote result based on Judge's decision. Requires careful timing/state management.
-   [ ] **`Majhool` (Group):** Implement complex group logic. Track group members. Night action adds a player. Check target faction: if Mafia, eliminate all group members. (Similar logic needed for `Freemason`/`Tyler`).
-   [ ] **`AdamSnowman`:** Implement night action 'Shoot' with use tracking (1 use). Check target: if Villager or `God F`, action fails, and the use is refunded (or bullet returned next night).
-   [ ] **`Gambler`:** Implement night action 'Double Ability' with use tracking (2 uses). Needs complex interaction logic to modify the effect (e.g., targets, impact) of the chosen player's action during resolution.
-   [ ] **`Link`:** Implement start-of-game action (or Night 1) to link two players. Persist link. Implement logic in elimination processing: if a linked player dies (night or day), eliminate the other linked player immediately.
-   [ ] **`Hunter`:** Implement night action 'Hunter Link'. Persist link (self to target). Implement logic similar to `Link`: if Hunter or linked target dies, eliminate the other.
-   [ ] **`PoliceChief`:** Implement day-death trigger. If eliminated during the day (vote/gun), announce role and allow a 'Last Shot' action targeting one player. If target is Mafia, eliminate them.
-   [ ] **`Revealer` (Villager):** Implement elimination trigger. If eliminated, announce role and cause of death.
-   [ ] **`CitizenSpecialist`:** Implement night action. Check if player count <= half total players. If so, allow Specialist to choose an eliminated Villager role and permanently become that role. Requires complex role/state change.
-   [ ] **`Commander`:** Implement night action 'Counter Sniper'. This action must resolve *after* the Sniper shot but *before* final night deaths are determined. Allow Commander to confirm/deny the kill (potentially saving a Villager target or confirming a Mafia kill). Handle Commander death if Sniper hits Villager (scenario dependent).
-   [ ] **`Elite`:** Implement night action 'Inquiry' with use tracking (1 use). Send PM to Elite revealing the role of one randomly chosen (or specified?) active Villager.
-   [ ] **`Gunsmith` (Villager):** Implement night action 'Arm Player'. Give a persistent "special gun" item to the target. Track gun holder. Announce gun holder during day start. Implement day action for gun holder to shoot (needs target selection). If not used, gun must be passed next night (requires night action for holder). Handle interaction with `Saboteur`.
-   [ ] **`Priest` (Villager - Bless):** Implement night action 'Bless' targeting multiple players. Mark targets as immune to `Natasha`'s silence for the next day. Potentially modify speaking time limits (if implemented).
-   [ ] **`Doppelganger`:** Implement night action 'Mimic'. Persist target. Implement logic on player elimination: if the eliminated player was the Doppelganger's target, change Doppelganger's role and abilities to match the eliminated player's. Complex state change.
-   [ ] **`Tyler` / `Freemason`:** Implement group logic. `Tyler` identifies `Freemason` on Night 1. `Freemason` uses 'Recruit' night action. Check target faction: if Villager, add to group and notify; if Mafia, eliminate all group members. Handle interaction with `Spy` (Mafia).
-   [ ] **`Inquisitor`:** Implement night action 'Inquire Team'. Check factions of two targets. Send PM result (same team / different teams).
-   [ ] **`Blacksmith`:** Implement night action 'Arm Player' (Armor). Grant target temporary immunity/protection during the *day* phase (e.g., immunity to guns, bombs?). Define how/when armor breaks or expires. Persist status.
-   [ ] **`CodeWriter`:** Implement night action 'Write Code'. Store submitted code (text) associated with the player. Needs mechanism for GM/Coordinator to view/use this info. May be low priority/manual.
-   [ ] **`RussianRoulette`:** Implement night action. Give persistent "roulette gun" item to target, store chosen number. Implement day logic: if gun holder uses it, trigger chain shooting based on the stored number. Complex day interaction.
-   [ ] **`Spider`:** Implement night action 'Weave' targeting multiple players. Persist the web link. Implement logic in day elimination processing: if any woven player dies *during the day*, eliminate all other woven players.
-   [ ] **`Bartender`:** Implement night action 'Intoxicate'. Mark target as 'drunk'. During the *next* night's action resolution, block the drunk player's action. Status clears after the block.
-   [ ] **`Saba`:** Implement night action 'Steal Role'. Temporarily grant Saba the target's role/abilities for 24 hours (until end of next night resolution?). Block target's abilities during this time? Complex state management.
-   [ ] **`Wizard`:** Implement night action 'Nullify' with use tracking (1 use). Mark target as 'nullified'. Block target's night action and potentially day abilities for the next 24 hours. Persist status.
-   [ ] **`Guardian`:** Implement passive abilities: 1) In Zodiac kill resolution, if target is Guardian, eliminate Zodiac instead. 2) If targeted by `Dynamite` bomb, automatically receive defusal info/survive.
-   [ ] **`Bomber`:** Implement night action 'Bomb' with use tracking (1 use), targeting 2 players for elimination. Implement passive trigger: if Bomber is killed *at night*, eliminate two random (?) players from their own faction (Villager).
-   [ ] **`Exposer`:** Implement day-vote-death trigger. If eliminated by day vote, allow Exposer to choose one player and publicly reveal their faction (Villager/Mafia/Independent).
-   [ ] **`Physician`:** Implement night action 'Antidote' with use tracking (track self-uses separately, max 2). If target was poisoned by `PoisonMaker`, negate the poison effect.
-   [ ] **`ToughGuy`:** Implement passive ability. In Mafia kill resolution, if target is ToughGuy and not previously hit, negate the kill but mark them as 'injured' (potentially block ability for that night?). Second Mafia shot kills. Persist 'injured' status.
-   [ ] **`Sacrifice`:** Implement trigger action 'Sacrifice'. Likely triggered during vote resolution (`apply_voting_outcome`). Allow Sacrifice player to choose to die instead of the player about to be eliminated by vote.
-   [ ] **`Sheriff`:** Implement night action 'Shoot'. Check target faction: if Mafia, eliminate target; if Villager, eliminate Sheriff.
-   [ ] **`NightWatch`:** Implement night action 'Inquiry Target' with use tracking (1 use). Requires tracking *who* targeted *whom* during the night. Send PM to NightWatch listing players who targeted them (names only).
-   [ ] **`Swordsman`:** Implement night action 'Gift Sword' with use tracking (1 use). Give persistent "sword" item to target. Recipient gains a one-time night kill ability (needs implementation). Track item holder and usage.
-   [ ] **`Jupiter`:** Implement night action 'Protect'. If target is chosen by `Yakuza` for conversion, block the conversion.
-   [ ] **`Ronan`:** Implement passive ability. If targeted by a night kill and *not* saved by Doctor, announce Ronan is injured during day start. Ronan can still vote until day voting concludes, then dies (or dies at end of day?). Clarify timing.
-   [ ] **`Avenger`:** Implement night action 'Guess Killer'. Compare guess to actual killer(s) from the night. If correct, grant persistent "gun" item to Avenger (needs implementation for usage).
-   [ ] **`MunitionsExpert`:** Implement night action 'Equip and Announce' with use tracking (1 use). Give persistent "weapon" item to target. Record 2 suspicious players for announcement. Implement day logic for weapon usage.
-   [ ] **`Investigator`:** Implement night action 'Investigate Faction'. Similar to `Kar Agah` but potentially without exceptions? Determine target's faction and send PM. Clarify interactions.
-   [ ] **`Executioner`:** Implement passive ability: Modify `apply_voting_outcome` announcement to hide the role of players eliminated by vote. Implement death trigger: If Executioner dies, announce their role.
-   [ ] **`Scribe`:** Implement night action 'Gift Pen'. Give persistent "pen" item to target. If target is killed that night, allow them to submit a "will" (text message stored/displayed?). Implement trigger: If Scribe reveals role (how?), grant `Sultan` (needs Sultan role defined) extra abilities.
-   [ ] **`WiseMan`:** Implement night action 'Save from Voting' with use tracking (1 use). Mark target as immune to entering the second round of voting (if implemented).
-   [ ] **`NightWanderer`:** Implement night action 'Hide'. Make player immune to all night actions (kills, investigations, etc.) for that night.
-   [ ] **`Ocean`:** Implement night action 'Wake'. Check factions of 2 targets: if both Villagers, notify them of each other; if Mafia or Zodiac chosen, eliminate Ocean during night resolution.

**Mafia Roles:**

-   [x] **`Mashoghe` (Lover):** Implement death trigger. If Mashoghe dies, set a flag allowing Mafia (`God F`) to kill two players the *following* night.
-   [ ] **`Joker`:** Implement night action 'Joker Action' (conditional on `God F` removed). Intercept `Kar Agah`'s investigation result for the chosen target and reverse it (Mafia->Villager, Villager->Mafia).
-   [ ] **`DoctorLec`:** Implement night action 'Save Mafia' (conditional on `God F` removed). Protect chosen Mafia member specifically from `Tak Tir` (Sniper) shot.
-   [ ] **`Natasha`:** Implement night action 'Silence' (conditional on `God F` removed). Mark target as 'silenced', preventing them from speaking/using commands during the next day phase. Handle interaction with `Keshish` (Priest - Unsilence) and `Priest` (Villager - Bless).
-   [ ] **`Terrorist`:** Implement day-death trigger. If eliminated during the day (vote/gun), allow Terrorist to choose one player to eliminate immediately ('Explosive Exit').
-   [ ] **`Mozakere` (Negotiator):** Implement night action 'Negotiate'. Check target eligibility (e.g., `ShahrSaD` or other specified roles). Potentially change target's faction to Mafia. Complex interaction/confirmation needed?
-   [ ] **`ShahKosh` (King Slayer):** Implement night action 'Guess Role'. Requires player to input target and guessed role. If guess matches target's actual role (and target is Villager?), eliminate target.
-   [ ] **`MaskedFigure`:** Implement night actions 'Freeze Investigation' (1 use) and 'Guess Role' (1 use). Freeze: Cause Detective investigating target to get neutral/no result. Guess Role: If guess is correct citizen role, transform target (how?). Implement passive: Always appears positive to Detective. Implement passive: Unknown to other Mafia initially.
-   [ ] **`DoubleFace`:** Implement passive: Always appears as Villager to `Kar Agah` (Detective). Modify Detective investigation logic.
-   [ ] **`Yakuza`:** Implement trigger 'Convert'. If Yakuza's role is revealed (how triggered?), allow them to choose one player to convert to Mafia, then eliminate Yakuza. Handle interaction with `Jupiter`.
-   [ ] **`MafiaSpecialist`:** Implement night action 'Revive Mafia' (conditional on player count <= half). Allow Specialist to choose an eliminated Mafia role and permanently become that role. Complex role/state change.
-   [ ] **`Butcher`:** Implement night action 'Convert Mafia' (1 use). Change the status/faction of *all previously eliminated* Mafia members back to Villager (implications?). Very unusual, needs careful design.
-   [ ] **`Thief`:** Implement night action 'Steal Role'. Copy target's night ability for use by Thief this night (or next?). Block target's ability? Complex state management.
-   [ ] **`Trickster`:** Implement night action 'Trick'. Check roles of 2 targets: if one is Doctor and one is Detective, kill the Doctor and "save" the Detective (how?).
-   [ ] **`Enchanter`:** Implement night action 'Enchant' with two modes: 1) Block target's night ability. 2) Place word curse: requires inputting a word. Monitor day chat; if target says the word, eliminate them immediately. Complex day interaction.
-   [ ] **`Saboteur`:** Implement night action 'Sabotage'. Mark target. If target uses a gun (`Gunsmith`, `Sniper`?, etc.) during day/night, eliminate the target instead of their shot succeeding. Needs interaction with gun mechanics.
-   [ ] **`PoisonMaker`:** Implement night action 'Poison' with use tracking (1 use). Mark target for elimination *two days later* (schedule job). Block Mafia kill action on the night poison is used. Handle interaction with `Physician`.
-   [ ] **`Spy` (Mafia):** Implement passive interaction with `Freemason`. If targeted by Freemason 'Recruit', change Spy's faction to Villager.
-   [ ] **`StrongMan`:** Implement night action 'Strong Kill' with use tracking (1 use). Requires confirmation from `God F` (if alive?). Kill bypasses immunity/toughness (`Ruyin tan`, `ToughGuy`).
-   [ ] **`Buyer`:** Implement night action 'Buy' (Night 1?). Requires Mafia discussion? Check target: if not Doctor, potentially change target's faction to Mafia (confirmation needed?).
-   [ ] **`NamelessMafia`:** Implement night action 'Assume Role' with use tracking (1 use). Allow player to choose any role (Mafia or Villager); gain that role's abilities for 24 hours. Complex temporary state change.
-   [ ] **`Dynamite`:** Implement night action 'Attach Bomb'. Mark target. Announce bomb during day start. Implement day interaction for target to choose sacrifice or defuse (needs defusal mechanic). Eliminate if fails/sacrifices. Handle interaction with `Guardian`.
-   [ ] **`LadyVoodoo`:** Implement night action 'Curse'. Requires target and word input. Monitor day chat; if target says the word, eliminate them immediately. Complex day interaction.

**Independent Roles:**

-   [ ] **`Zodiac`:** Implement night action 'Serial Kill' (even nights only). Check night number. Kill target. Implement night immunity (passive). Implement win condition. Handle interaction with `Guardian`.
-   [ ] **`Jigsaw`:** Implement night action 'Gas Chamber'. Choose 3 players, assign "saw" to one. Implement day phase sequence: announce targets, call to chamber, handle execution decision. Implement night immunity (passive). Implement win condition.
-   [ ] **`JackSparrow`:** Implement night action 'Curse' (effect TBD). Implement passive immunity to night kill and day vote. Implement win condition.
-   [ ] **`SherlockHolmes`:** Implement night action 'Sixth Sense' (first 2 nights only). Requires target and role guess. If correct, swap roles with target and eliminate target. Implement passive immortality for first 2 nights. Implement win condition (helps "third godfather"?).
-   [ ] **`Carrier`:** Implement passive infection spread on interaction (who chooses targets?). Track infection stages: Day 1 Silence -> Night 1 Ability Loss -> Day 2 Vote Block -> Night 2 Death. Implement win condition.
-   [ ] **`Werewolf`:** Implement night action 'Transform' with cooldown (3 nights). Change target's faction to Werewolf (or separate Wolf faction?). Implement win condition (convert half). Handle immunity interactions (Hunter, Priest?).
-   [ ] **`Syndicate`:** Implement passive knowledge (send role info at start?). Implement passive immunity to group attacks (Mafia kill?). Implement trigger 'Blacklist Kill': if Syndicate is in second vote round, allow kill from blacklist. Implement win condition.
-   [ ] **`Killer`:** Implement night action 'Assassinate'. Kill target, bypassing Doctor save. Implement win condition (last one standing?).
-   [ ] **`Corona`:** Implement night action 'Infect'. Mark target. Implement passive trigger: anyone targeting Corona at night becomes infected (dies next day unless saved by Doctor). Implement win condition.
-   [ ] **`Unknown`:** Implement passive ability: If targeted by a night action that implies recruitment (e.g., `Freemason`, `Buyer`?), join that player's faction/team. Implement win condition (must be chosen).
-   [ ] **`ThousandFace`:** Implement night action 'Mimic Ability'. Can choose to adopt ability of player eliminated during the *previous* day (for 24 hours?). Implement passive: Reflects night targeting back to the source. Complex state/interaction logic. Implement win condition.