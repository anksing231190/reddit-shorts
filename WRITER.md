# Daily writer instructions (Claude session, no API key)

A scheduled Claude session follows this file every day. It writes 4 original AITA-style stories (quality over volume: YouTube's inauthentic-content policy) and pushes them.
GitHub Actions (`Render AITA Shorts`) renders each one into `daily/<date>/`: a 1080×1920, 60 fps Short with the
story card, word-by-word captions and original runner-game gameplay behind it.

`DATE=$(TZ=Asia/Kolkata date +%F)`. If `scripts/$DATE/` already exists, stop: today is done.

1. **Avoid repeats.** Read `state/aita_log.json`. Don't reuse any earlier premise, conflict or twist.
2. **Write 4 drafts** as `drafts/01.json` … `drafts/04.json` (`drafts/` is not committed). Fields are listed at the
   top of `autopilot/finalize.py`. Rules:
   - **Original fiction only**, in the voice of an AITA post. No real people, brands, real places beyond cities,
     or copied Reddit posts. Make up a throwaway `username` (e.g. `seat_14A_throwaway`).
   - `post_title_candidates`: 3 different "AITA for …" / "WIBTA if …" lines, best first, specific and a little
     provocative, under 140 characters. The winner is read aloud first, so it is the hook: `hookscore.py`
     (yt-script) ranks them. Put the most outrageous concrete detail in it (a number, a relationship, an object).
   - `body`: first person, **420–540 words** (about 2:10–2:55 at the 1.25× narration speed; Shorts can be up to 3 minutes). Write ages/genders the AITA way, "I (27F)",
     "my husband (31M)". Short spoken sentences. Open straight on the conflict, build to one moment where someone
     says or does something outrageous, end on the fallout and why the narrator is unsure. At this length it needs a middle: a second escalation or a
     reveal about halfway (a text message, a relative taking sides, a receipt) so viewers don't swipe at 1:30. Leave the verdict
     genuinely arguable: the comments are the point.
   - Vary from day to day: family, weddings, money, roommates, work, in-laws, friends, neighbours, travel, dating.
     Mix narrators (about half female, half male) and ages. At most one revenge story per day.
   - Keep it advertiser-friendly: no sexual content, slurs, self-harm or violence; mild words only (the renderer
     softens the rest).
   - `closing`: usually "So, am I the a-hole? Tell me in the comments." Vary it now and then.
   - `title_candidates`: 10 YouTube titles, best first, under 60 characters, that do not start with "AITA" and do not
     give away the twist (e.g. "She Wanted My Window Seat for Free"). `thumb_text`: 2–4 words, different from the titles.
   - `premise`: one line describing the story, for the repeat log.
   - `description_first_lines`: two sentences with the words people search (yt-seo), and `search_queries`: the 3
     searches this Short should win. finalize warns if their words are missing from the title/description.
   - Loop (yt-shorts): the closing question should make the first line worth hearing again.
3. **Finalize each draft.** This runs the youtube-agent-skill `title.py` lint and picks the upload title:
   `python -m autopilot.finalize drafts/NN.json --out scripts/$DATE/NN.json`. Fix and re-run anything it rejects.
4. **Log them.** Append `{"date": "$DATE", "post_title": <the post_title in the finalized script>, "premise": ...}` for each to `state/aita_log.json`.
5. **Commit and push.** Commit only `scripts/$DATE/` and `state/`, with the message `AITA scripts for $DATE`, then
   `git pull --rebase && git push origin main` (retry up to 4 times). The push starts the render (about 25–35 minutes; the 4 videos render in parallel).
