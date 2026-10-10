# SoraSouls – Playtest checklist (build v72)

Thanks for testing! Play **offline**, back up your saves first (`%APPDATA%\DarkSoulsRemastered`), and start the game with `launchmod_darksoulsremastered.bat` in the ModEngine2 folder. See `README.md` for setup and the changed controls (Kingdom Key: R1 light, R2 heavy, **hold L1 + R1 to cast**).

For each item, write **OK** or describe what happened (where you were, what you pressed, a screenshot if possible).

## 1. New character (start a NEW Knight – these only apply to new characters)
| # | Check | Expected | Result |
|---|---|---|---|
| 1.1 | Starting stats | VIT 12, ATT 12, END 11, STR 11, DEX 13, INT 12, FTH 8, RES 7 | |
| 1.2 | Spell slots | 2 slots, Fire attuned | |
| 1.3 | Starting gear | Kingdom Key in the right hand, left hand empty, Sora's Hair/Jacket/Gloves/Shoes | |
| 1.4 | Roll | **Fast roll** with the starting gear | |

## 2. Feel
| # | Check | Expected | Result |
|---|---|---|---|
| 2.1 | Does Sora feel like Sora? | Nimble, dodge-first, Keyblade first and magic second | |
| 2.2 | Damage taken | Noticeably squishier than a normal Knight (light clothes) – too much? | |
| 2.3 | Keyblade melee damage | Too strong / too weak / fine? | |

## 3. Magic
| # | Check | Expected | Result |
|---|---|---|---|
| 3.1 | L1 + R1 cast | Always casts (also when pressing R1 right after L1) | |
| 3.2 | Spell origin | Spells and the cast glow come from the Keyblade tip | |
| 3.3 | INT scaling | Cast the same spell at the same enemy, level INT a few times: spells hit a bit harder | |
| 3.4 | Spell balance | Fire / Blizzard / Thunder: which feel too strong or too weak? | |

## 4. Movement
| # | Check | Expected | Result |
|---|---|---|---|
| 4.1 | High Jump | Running jump goes about chest-height higher | |
| 4.2 | Glide | Unlocks after the Bell Gargoyles; while falling, hold B / Circle (Space) to float down | |
| 4.3 | Sprinting on stairs | Normal (no floating) | |
| 4.4 | Lifts / elevators | Riding up feels normal, no sudden launch | |
| 4.5 | Fall damage | No fall damage when you glide to the ground | |

## 5. Looks
| # | Check | Expected | Result |
|---|---|---|---|
| 5.1 | Face | No other face showing through Sora's head – especially while guarding (hold L1) | |
| 5.2 | Anything else odd | Clipping, floating weapons, stretched parts | |

## 6. Drive Forms and abilities
| # | Check | Expected | Result |
|---|---|---|---|
| 6.1 | Drive Forms | Valor / Wisdom / Master / Final work and refill when resting | |
| 6.2 | "Sora learned …!" | Messages appear after the right bosses, on the message line above the MP / Drive bars (bottom right) | |

## 7. HUD messages (play in Borderless or Windowed mode)
| # | Check | Expected | Result |
|---|---|---|---|
| 7.1 | Messages don't block controls | Every SoraSouls message ("Sora learned …", Drive Form gained, Glide / High Jump levels, Anti Form, "Not enough Drive") shows on the line above the MP / Drive bars, and you can still attack and cast while it is showing | |

## 8. Donald & Goofy
Use the **Donald & Goofy** item to call them (use it again to send them away). They look like their KH2 selves: Donald carries his Mage's Staff, Goofy his Knight's Shield.

| # | Check | Expected | Result |
|---|---|---|---|
| 8.1 | Donald casts | In a fight, Donald casts sorceries (Soul Arrow / Heavy Soul Arrow) at enemies with his staff. He never uses a dagger or a shield | |
| 8.2 | Not in the way, mid-fight | During a fight and in doorways, walking into Donald or Goofy for a moment swaps him to a spot right behind Sora. While you fight **next to** them without walking into them, they should not be swapped away. They never fall through the floor | |
| 8.3 | Donald up close | When an enemy is right next to Donald, he swings his staff (or casts) – he never punches | |
| 8.4 | Goofy attacks with his shield | Goofy hits enemies with shield bashes (no mace) and still blocks with the shield | |
| 8.5 | Weapons in hand | Donald's staff and Goofy's shield sit in their closed gloves while idle, walking, attacking and casting | |
| 8.6 | After loading a save | Quit with Donald & Goofy in the party, reload: they appear by themselves within a few seconds | |

If the game crashes or acts strangely, also send `mod\sora_glide.log` (from the ModEngine2 folder).
