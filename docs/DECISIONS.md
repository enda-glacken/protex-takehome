# Decisions, assumptions and trade-offs

A running log of the decisions behind the prototype, kept as I built it with Claude Code. Later entries
supersede earlier ones; where they do, the earlier entry says so. Current figures are in the README.

## What the video actually shows (seen in stills and a 90s processed sample)

- One fixed camera labelled "IP Camera2", 28.5 minutes, 06:05 to 06:33, 1080p at 20 fps.
- A long conveyor runs diagonally across the frame. Freight is fed on at the bottom-right, from outside
  the frame, and travels up-left to workers who take it off and sort it into cages and onto the floor.
- So the camera sees **almost the whole belt and the pick-off crew, but not the truck or whoever is
  unloading it.** Only a hand is occasionally visible at the feed end.
- Typically 3 to 5 people in view. One often works the far side of the belt next to a large pile.
- In the 90s sample: 4.3 people detected per frame on average, mean confidence 0.75, wrists located
  well. The tracker produced 38 ids for about 5 people. Belt occupancy ranged 17% to 53%.

## Decisions

| # | Decision | Why | Alternative rejected | Trade-off accepted |
|---|---|---|---|---|
| 1 | Lead with **line state** (belt starved, flowing, backed up) alongside crew utilisation. "Backed up" later became "full flow" (17) and a stopped belt was added (15) | The customer's question is where to put a fixed number of people. An empty belt with people waiting says the constraint is upstream; a loaded belt says it is this crew. Utilisation alone cannot tell those apart. | Reporting utilisation and idle time only | Depends on the belt-occupancy estimate being decent |
| 2 | **Crew-level** metrics, no per-person scores | Tracker ids are not stable identities (38 ids for 5 people), and the question is about the operation. Per-person monitoring is also a trust and works-council problem. | Per-worker utilisation ranking | Cannot say "worker X is slow". Good. |
| 3 | **Rule-based activity** (handling / moving / waiting) from wrists, arm motion, body motion | Explainable to a customer, tunable in one config file, needs no labelled data | Learned action classifier; asking a vision-language model per clip | Cruder labels; must be validated by hand (evals) |
| 4 | **Hand-to-belt contacts** as the pace proxy; no parcel detector. Superseded by 17: no insight rests on contacts | Off-the-shelf models do not detect parcels reliably; the brief asks for off-the-shelf | Open-vocabulary parcel detection | Not a parcel count. Over-counts adjustments, under-counts two-handed lifts. |
| 5 | **Belt occupancy from belt colour**, sampled once a second | The belt is one uniform colour and nearly all of it is visible. Background subtraction was the first approach and was dropped: when the belt stops with freight on it, a background model learns the freight and reports a jammed belt as empty, which is the worst possible error for decision 1. | Background subtraction; parcel detector | Under-counts freight close to belt grey (dark bags). Area covered, not item count. |
| 6 | **Raw and derived layers** in one SQLite file | Detection is slow and done once. Zones and thresholds change often and re-run in seconds. | Parquet files; recomputing from video | JSON keypoints in SQLite are bulky (tens of MB for this clip) |
| 7 | **Static JSON to the app, no backend** | One clip, one viewer. Fewer moving parts to demo. | API server | Zone edits need a manual re-run |
| 8 | Sample at **5 to 10 fps**; app plays a **720p copy** | Activity changes over seconds, not frames. 720p with 2s keyframes makes jump-to-moment instant. | Every frame at 1080p | Fast hand movements between samples are missed |
| 9 | Composability through **seams, not frameworks** | A prototype should show where the seams are, not be built for scale. They are: raw and derived data; zones, thresholds and site context as config; each insight an independent rule over one table; the app and the skill touching only the store. | Plugin system, multi-tenant schema | A second video needs a small schema change |
| 10 | Skill is a **read-only query harness** with deep links into the app | Claude should compute from data, not recall; every answer should be checkable against video | Loading the whole store into the prompt | Canned commands may miss a question; raw SQL is the fallback |
| 11 | **Crew counts weighted by track coverage** per second | Counting distinct ids double-counts whenever the tracker swaps an id mid-second | Count distinct ids | Slightly smoothed counts |
| 12 | **Mock customer branding** from `config/site.json` | Makes it feel like the customer's product; also carries per-site wording (freight "taken off" vs "placed on" the belt) | Hard-coded copy | Must be labelled as fictional |
| 13 | A hand at the belt counts as handling **only if the arm is moving** | Spot check at 20:00: a man resting a hand on the belt rail and another sitting on the belt edge were both labelled "handling". Requiring arm motion fixed that moment (2 handling became 0, which matches the frame) and cut measured utilisation from 42% to 35%. | Wrist in zone alone | Slow, careful handling may be missed; the threshold (0.2) is a guess until the label eval |
| 14 | Add a **crew vs workload** insight over 2-minute blocks | The biggest pattern in the clip is a trend, not an episode: most people in view while the belt was emptiest, fewest while it was fullest (correlation -0.45 over 14 blocks) | Episodes only | A correlation over 14 blocks of one clip is suggestive, not proof; people who left the frame may have been working elsewhere |
| 15 | Detect a **stopped belt** from freight standing still between one-a-second thumbnails | I saw the belt stop at 18:55 and restart at 20:20; the system had called it "ran empty". The new signal put that stop at 18:47 to 20:19 and found 7 more (21% of the clip), with no reprocessing. Three of those eight later proved to be an empty, running belt (29). | Treating low occupancy as "starved" | Needs freight on the belt to tell; a stop on an empty belt is invisible. |
| 16 | **Drop low-confidence tracks** (average detector confidence under 0.5) | I saw a stack of parcels labelled as a waiting person at 4:43. That same spot produced phantom people repeatedly. | Keep everything the detector returns | People only partly in view at the frame edge are dropped too |
| 17 | **No insight rests on belt contacts**; "backed up" became "full flow"; staffing curve now counts people handling | I saw hands resting on the belt at 4:49, so contacts over-count. I saw 22:15 to 23:03 processing fine, so high occupancy with a moving belt is the line working, not a problem. | Peak pace and pace-by-crew-size from contacts | No pace measure at all without the customer's scan data |
| 18 | Superseded by 25. App organised around the operations manager's jobs: **Overview** (where the time went, where to act first), **Events** (the clips), **Rules and zones** (what is being looked for) | The first version led with a list of findings. A manager first wants to know whether the line ran, why time was lost and what to change; the clips are the proof, not the starting point. Rules and events are also how Protex's own product is described. | One page of video plus a findings list | More surface to keep truthful; Overview numbers depend on the unverified "waiting" label |
| 19 | **People are blurred by default** (each person, not the whole picture) | Protex describes automatic face and body blurring as its default. It also fits the crew-level stance. | Whole-frame blur toggle, off by default | Harder to see what a person is holding; can be switched off for review |
| 20 | **Opportunities ranked by waiting time, split by cause** (freight moving past, belt standing still, belt empty), each waiting minute counted once | Gives the manager one ranked list with a size on each item. On this clip at the time: crew size 65%, belt stops 26%, empty belt 10% of waiting (now 64%, 20% and 16%; see 27 and 29). | Ranking findings by severity labels | Waiting time understates belt stops, which also cost throughput; work away from the belt may be counted as waiting |
| 21 | **Video always on screen** with tiles and ranked actions beside it; **alert previews** per rule (the message and when it would have gone out); delivery channels are shown as labels and nothing is sent | Protex's own product pages show video with zones next to metric cards, a "Flow Stability" use case with jam time, and threshold alerts to Email, Slack and Teams. The belt-stop finding maps onto that use case. | Building real alert integrations; working-looking toggles that do nothing | Alerts are a preview computed after the fact, not a live system |
| 22 | **"Across your lines" panel**: when this line had people to spare or was short, measured against the crew size at which people working stops rising (5 here); other lines shown as not connected, with the destination left open (drawn as a chart in 26) | The customer's question is allocation across several lines. One line can supply half of it: when people were free. On this clip: about 1 person spare for 4 min 40 s, all in the first seven minutes; short by about 1 for 1 min 24 s, mostly near the end. | Inventing data for other lines; leaving the cross-line question unsaid | The spare figure is conservative and indicative; a real redeployment needs a second line short of people at the same time |
| 23 | **Page order: camera tabs, then this line's numbers beside the top three actions, then video beside three flagged clips, then detail** (timeline, events, rules, across your lines, breakdown). Cameras can be renamed; controls for cameras that are not connected say so when selected | A manager reads the answer and what to do first, then checks it against the video. Tabs make it plain which camera the page describes. | A debug layout with the video first and the numbers in a side tab; working-looking controls for cameras that have no footage | The video starts below the summary, so on a laptop it needs a scroll; camera names are saved in the browser only |
| 24 | **Timeline simplified to four labelled rows** (people in view with those handling freight, freight on belt, belt stopped, events) in 30-second averages; skeletons and zones off by default, blur and activity on; the numbers table replaced by **Export data** (headline figures, events, second-by-second timeline as CSV) | The earlier version stacked three activity colours, three event colours and red ticks with no key, and was hard to read. One idea per row with its label beside it needs no legend to decode. Export gives an analyst the exact figures. | Keeping the handling, moving and waiting split on the chart; a per-second chart | Moving and waiting are merged on the chart (the split is still in the breakdown and the export); 30-second averages hide short spikes; the belt-stop test is repeated in the web app, so a change to the threshold in config has to be made in both places |
| 25 | **Review happens at the video** (supersedes the Overview, Events, Rules tabs in decision 18): a panel beside the video, the same height as it, explains the selected event (what happened, why it matters, what to try), takes the manager's call (needs action, no action needed, not what happened) and moves to the next one. Events are a one-line-each queue with a progress count; patterns and benchmarks are listed separately as reference. The Overview tab is removed because it repeated the top actions; redeployments moved into "Across your lines". **Rules became Alerts**: for each alert, when it tells you, why that helps, when it would have reached you in this recording, and an example message | The old flow made the manager scroll between the clip and the event card, and mixed problems with benchmarks. The calls are also labels: "not what happened" is a free accuracy check from the customer, and the events export carries them. A manager does not want rules; they want to be told in time to act. | Expanding cards in a grid; a rules list with definitions and thresholds up front | Calls are saved in the browser only; alert times for two of the three alerts cover only the longest cases, because the pipeline lists the largest events of each kind; alerts are computed after the fact, not sent |
| 26 | **The manager can narrate or type what they saw on each event**, saved with their call and included in the events export. **Potential redeployments drawn as a chart**: the connected line's spare-person windows as solid blocks, with a matching dashed, empty slot at the same times for the lines that are not connected | The manager knows why a belt stopped; the camera does not. Their account, attached to a timestamped event, is the richest label the system can get, and it costs them a sentence. The empty slots make the case for connecting more lines without inventing data for them. | A whole-video narration session (does not scale, and not tied to events); a table of redeployments with the destination column blank | Narration uses the browser's own speech-to-text, so it needs Chrome, Edge or Safari and the audio goes to that browser's speech service; notes are stored in the browser only; nothing yet feeds the notes back into detection |
| 27 | **Top action reframed from "Match the crew to the work" to "Open a second working position"**, and "Labour idle" reworded to "Crew waiting" with a note that it may include work away from the belt | The old action was sized at 45 minutes of crew time but its remedy, running with 5, frees about 1 person for 4 min 40 s. The data says the limit is places to work: about 4 people stood at the sort end while freight flowed and about 1.5 were handling at a time. "Idle" was a hard word on a measure that is within one person 9 times in 10. | Keeping the larger-sounding claim | The position suggestion comes from one coarse zone; where a second position should go needs positions along the belt and a trial |
| 28 | **Threshold check and review read-back added** (`evals/sensitivity.py`; skill command `reviews --file`), and "worker-minutes" replaced with "minutes of crew time" | The thresholds were set by eye, so the honest question is whether the findings move when they do. They mostly do not: people handling with 6 or 7 present stays within 0.2 of the figure for 5 in all 11 variants, and the top action is the same; the stop count and the waiting share move. Reading the manager's exported calls back through the skill is the first step of using reviews as labels. | Reporting single figures as if they were exact | Each threshold is moved one at a time, not in combination; reviews are read, not yet used to retune anything |
| 29 | **A pause counts as a belt stop only if the belt had freight on it at some point in the pause** (more than 10% covered). Belt stops went from 8 to 5 and downtime from 21% to 17% | I watched all eight detected stops on 16 Nov. Five were real; three, in the first five minutes, were an empty running belt with the crew waiting for the next cart. On an empty belt nothing moves in the picture either way. Those periods are now reported as belt empty with crew waiting, and waiting by cause is 64% freight moving, 20% belt stopped, 16% belt empty. | Leaving the larger figure in | A real stop on an empty belt is now invisible; the 10% line was chosen on this one clip (the three false stops peaked at 8% cover, the lowest real one at 20%) |
| 30 | **A small design system** (`docs/DESIGN_SYSTEM.md`): neutral chrome, one typeface (Outfit), one accent (floor-tape yellow), pill navigation, figures on quiet tiles; colour reserved for data (ink is work being done, yellow is waiting or spare time, red is belt downtime; the charts, timeline and video labels were moved to this palette afterwards) | The interface had grown by request and carried three blues and two typefaces. One set of tokens makes it read as one product and makes the data colours mean something. Direction taken from reference dashboards I collected. | Copying the reference's green, glass cards or layout | Applied as a layer over the earlier styles, which should be folded in; no dark theme; no spacing scale |

## How the headline figures changed

Each change came from checking the system against the video, not from tuning towards a number.

| Stage | Belt | Crew time | What changed |
|---|---|---|---|
| First full run, 15 Nov, unverified | Belt empty while staffed: 17% | 35% handling, 53% waiting | First-pass zones and thresholds |
| After watching four moments, 15 Nov | Belt stopped: 21%, 8 stops | 36% handling, 52% waiting | Belt-stop detection added; a parcel stack no longer counted as a person; hand-to-belt contacts dropped as a measure |
| After watching all eight stops, 16 Nov | Belt stopped: 17%, 5 stops, 4 min 58 s | 36% handling, 52% waiting | Three "stops" were an empty, running belt; the rule now needs freight on the belt |

Where this leaves the recommendation: open a second pick-off position so more of the crew can reach freight; find out
who stops the belt and why, starting with the stop at 8:51; and share scan data for the same half hour so throughput
can be checked.

## Assumptions, and how each would be tested

| Assumption | How to test |
|---|---|
| A wrist over the belt zone means the worker is handling freight | Label eval (`evals/`); watch 10 belt contacts |
| People in view are all part of this line's crew | Ask the customer; check for walk-throughs in the clip |
| Belt colour is constant across the clip (lighting does not change) | Compare the empty-belt colour at the start and end |
| 28.5 minutes at 06:05 is representative | It is not, by itself. Ask for a full shift, and a peak day. |
| The feed end (off camera) is the truck unloading point | Ask; or look at Camera 1 |
| Belt cover and belt motion describe what the belt is doing | All five reported stops watched; compare with the customer's scan data for the same half hour |

## Verification log: what I watched and what changed

**15 Nov, the first moments I checked**

| Moment | System said | I saw | Outcome |
|---|---|---|---|
| 4:00 to 6:00 | Belt near-empty, 6 to 7 people | Packages enter from 4:33 and flow until about 6:00 | Partly right. The system then read 4:12 to 4:38 as a belt stop; on 16 Nov that proved to be an empty, running belt (below) |
| 18:30 to 20:30 | "Belt ran empty", 4 waiting | Belt stopped 18:55, restarted 20:20 | System was wrong about why. Fixed: stop detected 18:47 to 20:19 |
| 22:15 to 23:03 | "Freight backed up" | No pile-up, processing fine | False alarm. Now "full flow", used as the benchmark |
| 4:49 | Counted as picks from the belt | Two hands resting on the belt | Contacts over-count. No insight uses them now |
| 4:43 | A "waiting" person at the right of the belt | A stack of packages | False detection. Low-confidence tracks dropped |
| Belt end | Not modelled | Two people scan at the belt end | Matches the data: about 2 people handling whether 5, 6 or 7 were present |

**16 Nov, the five belt stops not yet watched**

| Stop | I saw | Outcome |
|---|---|---|
| 1:33 to 1:54 | Belt moving with nothing on it; the crew waiting for the next cart | Not a stop. Now reported as belt empty with crew waiting |
| 2:36 to 2:56 | Belt moving with nothing on it until a cart was unloaded | Not a stop |
| 4:12 to 4:38 | Belt moving but empty until the next package at 4:31 | Not a stop |
| 12:27 to 12:48 | Belt stopped; cause not visible | Real |
| 14:59 to 15:31 | Belt stopped over a question about a label, to avoid a pile-up | Real |

Still unverified: the 36% handling figure beyond ten labelled moments, and whether people near the carts are working
when they are labelled waiting.

## My unaided observations (first five minutes, written before seeing any results)

| I saw | What the data says | Status |
|---|---|---|
| 4 people idle at 2:10 | 2:00 to 2:20: 6.5 in view, 2.0 handling, 4.3 waiting, belt 10% covered | Agrees |
| Lots of idle time watching the belt | 53% of worker time labelled waiting | Agrees in direction; the label eval gives the number |
| Bulk of packages acted on at the end of the belt | 57% of hand-to-belt contacts fall in the first fifth of the belt, 83% in the first two fifths | Agrees |
| Worker at belt end scans, then throws into the cart | Not measured. Implies one scan point that everything passes through | Candidate cause of the idle time: test it |
| A few seconds lost each time a cart is swapped | Not measured (no cart zone) | Next step: a cart zone and changeover events |
| Man jumps on the moving belt around 2:50 | Stored poses show legs inside the belt zone around 2:40 to 2:50, and strongly at 20:00 (a man sitting on the belt edge) | Rough signal from existing data, no reprocessing. Noisy: far-side workers' legs also overlap the belt |
| Open sandals, packages thrown, packages over the edge and under the belt, messy floor | Not measured | Safety and housekeeping: Protex's core products, same camera |
| Inconsistent uniforms; coloured ones would track better | Not needed for crew-level metrics | Not pursued: nothing here needs to know who is who |
| A man at the belt end standing still and blocking the view | People are masked out of belt occupancy; no per-person reporting | Not reported: nothing is reported per person, and his role is unknown |

## Label eval (16 Nov): 10 moments, one every three minutes, labelled before looking at the system

- People present: exact 4 of 10, within one 9 of 10, average error 0.7. The system never over-counted.
- People handling: exact 4 of 10, within one 9 of 10, average error 0.7. System lower in 5, higher in 1.
- Handling share at those moments: 31% by hand (17 of 54), 26% by the system (12 of 47).
- By hand, handling averaged 1.75 with 6 or 7 present and 1.67 with 4 or 5 present: more people, no more work done.
- Conclusion: the system undercounts, the direction of the findings holds on independent labels, and ten moments is a start, not a validation.
