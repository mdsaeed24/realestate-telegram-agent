Read @PROJECT_BRIEF.md and @CLAUDE.md before anything else.

The brief describes what this agent is for and how the conversation should go.
CLAUDE.md has the architectural rules and the constraints that cause silent
failures. Treat the brief as the source of truth for behaviour. Where it gives
a reason for a choice rather than a rule, respect the reason.

Before asking me anything, use the Supabase MCP to inspect the real-estate
storage bucket. One folder exists, Sobha Magnolia, holding hero.jpg,
image1.jpg through image4.jpg). Write the spec against what is
actually there.

Three things that are already decided, do not reopen them:

- The bucket is public. Telegram fetches media by URL without our auth headers, so
  private storage would mean signed URLs with expiry, which breaks whenever a
  cached media id needs refreshing.
- Only one property has media. The other four seeded properties will have no
  media folder. The agent must handle a listing with no media by sending the
  details as text and saying photos are not available for that one yet. Spec
  this as normal behaviour, not an error case.
- The media folder is its own field in the schema, never derived from the
  property id, so adding media for the other four later is a data change and
  not a code change.

Then interview me using the AskUserQuestion tool. Ask about implementation,
data schema, edge cases, failure modes and tradeoffs. Do not ask questions the
brief already answers. Dig into what it does not cover:

- what happens when a lead goes quiet mid conversation
- what happens when someone asks about a property that does not exist
- what happens when the same lead messages again a week later
- how media reuse works across leads, and when a cached media id is refreshed
- how language is detected and whether it holds across a whole conversation
- what happens when a lead asks for a budget or area we have nothing in
- what happens when two leads book the same slot
- what state lives in Supabase versus what is derived fresh each turn

Keep interviewing until we have covered everything. Then write BUILD_SPEC.md
in the project root. Name the files and interfaces involved, state what is out
of scope, break the work into phases in dependency order, and end each phase
with a verification step I can run that proves it works before moving on.

The Google Sheet does not exist yet. Its schema is part of what the spec must
define, and creating and seeding it should be an early phase of the build.
Properties and leads both live in Sheets so the client can edit them. Supabase
holds media, conversation state, media id cache, and bookings. I will setup the google cloud project and upload the credentials.json file and share the sheet ID in env.example file. I will share the service account email with google sheet. You will have to then create this google sheet for me with relevant sheet tabs and columns.

Before the media phase, the spec must include an ffprobe check on video.mp4 to
confirm H.264 video, AAC audio and a single audio stream. A video violating any
of these returns HTTP 200 and never arrives.

create .env.example file for storing all the keys and access token from time to 
time as the project gets upadated. 

Build this project autonomously and carry out the phases. Start a cloud flared tunnel and also share the call back URL once it is done so that I can update in Telegram's dashboard.