# Petty Neighbors

The show bible. Every skit agent reads this first. Rulings come from Caleb's grilling of
2026-10-14; change them only on his word.

## What it is

Vertical (9:16) painterly 3D animated skits, 30 to 60 seconds, about animals living in one shared
neighbourhood. Broad but adult-aware comedy: brand-safe, no swearing, jokes that land for adults
and are safe for anyone. It is an open universe: more casts and storylines will arrive, and not all
of them will be about this building.

**The Ninth Room is the studio's internal name. It never appears on the show:** not in a
caption, title, description, on-screen text, voice line or channel copy.

## The look

Painterly 3D, chosen by Caleb on 2026-10-14 after a motion test. It replaced Higgsfield's default
glossy 3D, which he had already seen in other people's shorts. **Every image and video prompt pastes
this style block word for word:**

> Painterly stylized 3D animation: sculpted 3D forms rendered with visible hand-painted brushstrokes, fur and feathers painted as broad clumped gouache strokes rather than individual hairs, soft painted edges, a muted earthy palette, an illustrated storybook brought to life. Matte, no gloss, no plastic sheen, no photoreal fur. The same painterly style in every frame.

**Nobody else's prompt can make our characters.** Oso and Prince are drawn from Caleb's own dogs.
Every invented character carries signature details a generic prompt would never produce: an
asymmetry, a mark with a story, a habit of grooming or posture, a specific object. A character that
could come out of "a cartoon pigeon" is not finished.

## Arcs

Each skit follows ONE protagonist from one arc. The other main character cameos in about one skit
in three (seen through the window, or the building in the back of the alley). Full crossovers are
saved for big moments.

| Arc | Protagonist | Premise |
|---|---|---|
| High Rise Living | Oso | Just moved from a suburban house with a big yard into a walk-up of three storeys plus a roof that the other pets insist on calling "high rise living". Lives on the SECOND floor. Dogs on the upper floors, with the better view, are the Top Dogs. Oso plays aloof while quietly wanting in. |
| Alley Rules | Mags, the alley cat | An OG of the alley behind the dog's building. Has seen a hundred "high rise" newcomers come and go. Knows the building is three storeys plus a roof. |

**Series goal:** the roof, the one place above even the Top Dogs. The dog wants the view; the cat
already goes there; neither says so. Skits stand alone; the roof is a slow payoff.

## Cast

Six recurring characters. Files in `cast/<id>.md`, approved by Caleb.

| Character | Who | Arc |
|---|---|---|
| Oso (OH-so) | 14-year-old Cane Corso, the lead. Aloof and slow, though not too slow. At rest, a sliver of his tongue shows. Not a gloom character: he is unimpressed, not sad. | High Rise Living |
| Prince | Caleb's own dog, drawn from his photos. A 15-year-old female lab mix, long body on stubby legs, right eye lost to glaucoma. Her real name is Princess; she goes by Prince. A lesbian, rough around the edges. Oso's second-floor neighbour and the building's gruff veteran. | High Rise Living |
| Duchess | mastiff, the alpha Top Dog | High Rise Living |
| Pip | Pomeranian, Duchess's sycophant | High Rise Living |
| Mags | old alley cat, the second lead | Alley Rules |
| Ziggy | gossip crow, Mags's rival and informant | Alley Rules |

Clyde, the old basset hound, is a guest character now.

**Prince's identity** shows the way any character's life shows: her crushes, her history, her
opinions. Being a lesbian is part of who she is and never the punchline. Her toughness, her one eye
and her age drive her comedy.

Guest animals are one-offs with sheets made only when a script needs them.

**Humans** appear only as legs, offscreen voices or from behind. Animals talk only to animals.

**Voices:** no ethnic accent or dialect for any character. Toughness is attitude and wear.

## Sets

Five plates, each in `sets/<id>.md`:

1. Building front and stoop
2. The dog's unit interior (second floor)
3. Stairwell and lift (the lift is chained shut, out of order since forever)
4. The Top Dogs' upper balcony
5. The alley behind the building, with the dog's window visible

## Production rules

- Seedance 2.5, 9:16, 10 second generations with up to two planned internal hard cuts; a skit is
  four to six generations.
- Every shot is drafted first; only approved drafts are finalised, at 720p.
- Cap: 500 credits a skit, drafts, finals and re-rolls included. Every paid batch shows its
  estimate and waits for Caleb's go.
- Dialogue is native to Seedance; each character's voice prompt is pasted verbatim.
- Assembly with ffmpeg; captions burned in from the script text; music and SFX from the existing
  libraries.
- Gates: script (in the CLI), then drafts, finals and the cut (on the Skits desk).
- Every post ticks the platform's AI-generated label and carries a line in its description.
- Channels: `@pettyneighbors` on YouTube, Instagram and TikTok.

## Where things live

| Path | What |
|---|---|
| `shows/petty-neighbors/show.md` | this bible (tracked) |
| `shows/petty-neighbors/cast/<id>.md` | look anchors, master profile, voice prompt, sheet prompt, approved reference job ids |
| `shows/petty-neighbors/sets/<id>.md` | look anchors, location map, plate prompt, approved reference job ids |
| `shows/petty-neighbors/pitches/<date>.md` | the week's five loglines |
| `work/_shows/petty-neighbors/refs/<id>/` | downloaded reference images (untracked) |
| `work/<skit-slug>/script.json` | the script (untracked) |
| `work/<skit-slug>/shots.json` | the Seedance prompts and estimates (untracked) |
