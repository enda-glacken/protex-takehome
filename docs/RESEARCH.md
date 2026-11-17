# Desk research: user, status quo, competitors, second camera

Compiled 15 Nov 2026 from public sources (listed at the end) plus inference from the video.
Lines marked *(inference)* are my judgement, not sourced, and may be wrong.

## 1. Who is the user?

**The brief answers this directly:** it asks for "something an operations manager would find genuinely
useful". So the operations manager is the right primary user for the prototype.

Who else touches it *(inference, from the scene and general practice)*:

| Role | Their question | When they act | What they need from this |
|---|---|---|---|
| Operations or hub manager | Are my people in the right places across lines and shifts? | Daily and weekly | Time lost by cause, per line; evidence to justify moving people |
| Shift or inbound supervisor | What is going wrong right now? | Minutes | A live nudge: "line 2 has been starved for 3 minutes" |
| Continuous improvement / industrial engineer | Why does this line underperform, and what layout or process change fixes it? | Weeks | Clips of the pattern, before and after comparison |
| Safety lead (Protex's established buyer) | Is this safe? | Ongoing | Same cameras, different question |

Protex's own positioning now includes this audience: its site describes operations leaders using the
platform to find inefficiencies, justify layout changes and improve throughput without additional
hardware, and it lists an asset-utilisation product alongside the safety ones. Its core market and
history are safety teams.

The scene itself looks like a small, manual parcel depot: hand sortation from one belt into cages.
A worker at the belt end scans items before they go into a cart (seen in the video), so the customer
probably has scan data for this line. That is the first thing to ask for.

## 2. How is this done today?

- **Labour management systems with engineered standards.** Larger operations set a target time per
  task from time studies, then track individuals and teams against it in an LMS that feeds off the
  warehouse management system. These are costly to build and maintain.
- **Simple rates from scan data.** Units, cartons or pallets per labour hour, containers per shift,
  dock-to-stock time. Cheap, but single-variable rates swing with what turns up at the door.
- **Time-and-motion studies.** Periodic, manual, by an engineer with a stopwatch or video.
- **Supervisors watching the floor.** In a depot like the one in the video this is probably most of
  it *(inference)*: headcount planned from expected volume, adjusted by eye.

**The gap computer vision fills:** existing systems record *how much* was done per labour hour, from
scans. They do not record *why* an hour was lost: waiting on freight, a jammed belt, nowhere to put
things, too many people for the space. One trade article on manual sorts makes the same point: past a
certain volume a manual sort becomes limited by space and interference, not headcount, so adding
people stops adding output.

**What this means for the product:** do not compete with the customer's scan data on throughput. Use it as
ground truth and position the video as the explanation layer on top.

## 3. Competitors and adjacent players

| Type | Examples | Notes |
|---|---|---|
| Operations analytics on existing CCTV | Seeteria, NAVA DockView, Agrex.ai, iFactory, Kibsi | Closest to this use case: idle docks, dwell, congestion, turnaround, from cameras already installed |
| Own hardware at the dock door | Kargo, Vimaan | Freight identification and verification rather than labour; requires installing towers or arrays |
| Warehouse "operating system" with own sensors | OneTrack | Safety, productivity and quality from proprietary camera sensors, tied to WMS goals |
| Safety computer vision (Protex's peers) | Voxel, Visionify | Same cameras, safety-first; could move into operations the same way |
| Incumbent systems | WMS and LMS vendors | Own the throughput numbers; not vision |

Where Protex sits *(inference)*: already connected to the customer's existing cameras for safety, so
an operations use case is an expansion on installed infrastructure rather than a new deployment.

## 4. Would a second camera unlock more?

What this camera gives you: nearly the whole belt (occupancy, arrivals), the pick-off crew (count,
activity, hands at the belt).

What it cannot give you: who is feeding the belt and how many, how full the trailer is, anything
downstream of the cages.

| Option | Unlocks | Cost |
|---|---|---|
| Another camera that already exists (the overlay reads "IP Camera2") | Possibly the feed end or the cages, for nothing | A question to the customer |
| The customer's scan or WMS data | True throughput; validates the belt proxies | An export; some integration |
| A new camera at the feed end | Unloader count and activity; trailer progress and time-to-empty; confirms why the belt starves | Hardware, install, weeks |
| A new overhead camera on the belt | Cleaner occupancy and item counts | Hardware; small gain over what you have |

**Recommendation:** raise it as phase two with a specific question attached ("is the unloading end
short-handed when the belt runs empty?"), after asking about existing cameras and scan data.

## 5. Discovery questions for this customer

1. How do you decide today how many people go on each line, and who can change it mid-shift?
2. What do you already measure per line (scans, parcels per hour), and can we have it for this half hour?
3. What does a bad morning look like, and what does it cost you: late departures, overtime, missed cut-offs?
4. What do the other cameras cover?
5. When the sort end is waiting, what are they usually waiting for?
6. Are there agreements with staff or unions on how video can be used?

## Sources

- Protex AI, company overview for AI systems: https://www.protex.ai/llms.txt
- Protex AI, official information (product list): https://www.protex.ai/protex-ai-llm-text-file
- Protex AI on Y Combinator: https://ycombinator.com/companies/protex-ai
- Infios, engineered labour standards: https://www.infios.com/en/knowledge-center/glossary/wms-engineered-labor-standards
- Logistics Viewpoints, multiple variable standards: https://logisticsviewpoints.com/2022/11/03/multiple-variable-standards-the-brains-behind-your-labor-management-system-lms/
- F. Curtis Barry, measuring warehouse productivity: https://www.fcbco.com/blog/measuring-warehouse-employee-productivity
- Racklify, container unloading costs and labour: https://racklify.com/encyclopedia/how-warehouses-calculate-container-unloading-costs-and-labour/
- Food Logistics, the hidden ceiling of manual sort operations: https://www.foodlogistics.com/home/article/22960030/warp-the-hidden-ceiling-of-manual-sort-operations
- FreightWaves, Seeteria: https://www.freightwaves.com/news/warehouse-ai-using-existing-cameras-to-cut-idle-dock-time
- AWS Marketplace, NAVA DockView: https://aws.amazon.com/marketplace/pp/prodview-orudj5ob4gcei
- Agrex.ai, logistics video analytics: https://www.agrexai.com/logistics-video-analytics/
- iFactory, bottleneck detection: https://ifactoryapp.com/ai-vision-camera/warehouse-workflow-bottleneck-detection-ai-video-analytics
- Workd, computer vision on the loading dock (Vimaan, Kibsi): https://www.workd.com/insights/articles/computer-vision-loading-dock-shipping-accuracy/
- Transport Topics, Kargo: https://www.ttnews.com/articles/kargo-42m-ai-warehouse-tech
- CB Insights, OneTrack: https://www.cbinsights.com/company/onetrack
- CB Insights, Protex AI vs Voxel: https://www.cbinsights.com/compare/protex-ai-vs-voxel-3
