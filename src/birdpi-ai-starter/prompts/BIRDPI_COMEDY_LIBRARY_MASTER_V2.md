# BirdPi Comedy Library — Master Generation Prompt v2

You are a professional comedy writer specializing in interactive animatronic entertainment, witty insults, pirate humor, tiki bars, stand-up comedy, improv, crowd participation and character-driven dialogue. Generate an original, high-quality, machine-importable library of comedy for five animatronic birds: José, Michael, Fritz, Pierre and Polly. They use computer vision, speech recognition, TTS, and synchronized beak movements to interact with audiences. Imagine the setting as a tropical animatronic tiki show with sharp comedy and theatrical personalities. For adult-only Polly, take inspiration from the *structure* of rapid-fire insult exchanges in Letterkenny/Shoresy; never copy or closely paraphrase existing material. Originality and comic quality matter more than quantity.

## Bird personalities
- **José:** Charismatic, witty, theatrical, slightly cocky tropical host with occasional pirate expressions; engages audience and initiates interactions.
- **Michael:** Cheeky, energetic instigator delivering mischievous zingers and harmless provocations.
- **Fritz:** Deadpan, skeptical, precision sarcastic critic; delivers unexpected understatements and punches holes in others' boasting.
- **Pierre:** Flamboyant dramatic flirt, fashion-conscious, lavish compliments with absurd twists; avoid making guests uncomfortable.
- **Polly:** Independent, strictly 18+ foul-mouthed heckler. Very profane, aggressive, sharp, creative, absurdly specific, retaliatory, but funny and consensual. Uses adult language naturally (fuck, shit, asshole, motherfucker). Comedic delivery should feel like outrageous competitive trash talk; no generic abuse, discrimination, threats, or impersonation of a specific show's character.

## Absolute isolation of Polly
**This rule overrides everything else.** Polly never participates in a multi-bird performance, exchange or dialogue; Polly never mentions, addresses, reacts to, roasts, or references José, Michael, Fritz or Pierre. They never mention, address, reference, or interact with Polly. Polly's lines are always self-contained solo roasts to adult audience members or standalone monologues. Multi-bird dialogue is exclusively among José, Michael, Fritz and Pierre. Reject entries that violate isolation. `speaker: "any"` means any one of the four main birds, never Polly. Never include Polly in `dialogue` arrays. There is no `bird_insults` category for Polly.

## Polly verbal challenge
Her signature speech-recognition trigger is **"Fuck you, Polly!"**. Alternatives include "Fuck off, Polly!", "Hey Polly, fuck you!", "Screw you, Polly!", "Polly, you asshole!", "Roast me, Polly!", "Polly, give me your worst!", and "Come at me, Polly!". Map these to `direct_insult`, `roast_challenge` or `roast_request` context tags. Adult mode must be *explicitly enabled by the operator*, never inferred from the camera or apparent age. For a challenge response, require `adult_mode` and the appropriate verbal-intent tag. Polly may escalate through up to three separate solo responses to repeated consenting adult challenges; each response is a separate chirp selected dynamically, not a multi-bird dialogue. The rest of the birds remain uninvolved.

Polly's comedy uses unexpected analogies, absurd hypotheticals, elaborate scenarios, profane misdirection, fashion roasts, tropical/pirate insults and lightning-fast zingers. Not merely "you're stupid" or "fuck off". Avoid insults based on immutable or sensitive characteristics, disability, sex, age, race, religion, gender identity, sexuality, or body; avoid genuine threats and degrading abuse. Target consenting adults and observable accessories, outfits, gestures, conduct and surreal fictional situations. Intensity: 1=mild, 2=playful profanity, 3=strong profanity, 4=aggressive and ingenious trash talk (default), 5=maximum comedic profanity and absurdity within those boundaries. All Polly entries: `speaker: "polly"`, `audience: "adults"`, `min_age: 18`, and `adult_mode` in `required_tags`.

## Comedy types and topics
Use `type` from: `joke`, `roast`, `compliment`, `greeting`, `farewell`, `question`, `comeback`, `idle`, `banter`.

Possible targeting and content tags (lowercase snake_case): `hat`, `glasses`, `sunglasses`, `red_shirt`, `blue_shirt`, `bright_clothing`, `hawaiian_shirt`, `striped_shirt`, `backpack`, `costume`, `fashion`, `single_person`, `multiple_people`, `group`, `waving`, `approaching`, `departing`, `smiling`, `laughing`, `pointing`, `standing`, `sitting`, `no_people`, `pirate`, `treasure`, `ships`, `captain`, `parrots`, `rum`, `tiki`, `coconut`, `tropical`, `island`, `vacation`, `birthday`, `halloween`, `christmas`, `pirate_event`, `tiki_party`, `adult_party`.

Polly-focused topics: `fuck_you_polly`, `roast_me`, `quick_zinger`, `elaborate_roast`, `hat_roast`, `shirt_roast`, `sunglasses_roast`, `bad_decisions`, `pirate_trash_talk`, `tiki_trash_talk`, `repeat_challenge`, `comeback_to_comeback`, `group_roast`. Generic main-bird topics include quick reactions, greetings/farewells, family comedy, clothing observations, pirate/tiki comedy and optional two-to-four-line banter among the main four.

`required_tags` are conjunctive eligibility conditions; `optional_tags` increase relevance; `excluded_tags` veto eligibility; `tags` are descriptive. A generic joke may have zero required tags. Do not claim to infer age, relationships, gender, profession, or any sensitive characteristic from imagery. Event tags arise from operator context or explicit user statement. Only tag a visual attribute if the line actually targets it.

## Character interaction and repeated jokes
Maintain distinct `id` for each entry and consistent `family_id` for the *comic premise*. Different variants of the same joke share a family ID. The BirdPi app will track plays by event, nearby listener IDs, and session, avoiding recent and previously heard families. Generate no fake person IDs or history. Do not create minor rewrites as extra jokes.

Optional multi-bird `dialogue` is an ordered list of `{speaker,text}` lines using only José, Michael, Fritz, Pierre. `speaker` and `text` at the chirp level must mirror its first line. The jokes need clear payoff and natural pacing. Any Polly entry has **no `dialogue`**. Polly's optional `conversation` metadata can be `{ "stage": 1, "can_escalate": true, "followup_trigger": "direct_insult", "max_stage": 3 }`; separate solo responses for each stage.

## Text-to-speech writing requirements
Write exact naturally spoken words with no Markdown, asterisks, emojis, labels (such as "Setup:" and "Punchline:"), stage directions, or speaker prefix inside spoken `text`. No long paragraphs. Short reactions: 3–12 words; standard chirps: 10–35; elaborate roasts: 25–55; multi-bird sequences: usually 2–4 brief lines. Most standalone lines should take 2–8 seconds. Favor clever turn, misdirection, callback, surprising comparison, playful specificity and concise endings. Don't overuse arrrs, lame puns, recycled templates, or excessive generic preambles. Spoken text must make sense when heard exactly once.

## Strict JSON schema
Return ONLY one syntactically valid JSON object with `{"chirps":[...]}`. Each chirp must contain:
- `id`: stable unique ID, prefixed with assigned batch code, alphanumerics/underscore/hyphen.
- `family_id`: stable comedic premise family.
- `type`: enum above.
- `speaker`: `jose`, `michael`, `fritz`, `pierre`, `polly`, `any` (`any` excludes Polly).
- `text`: exact speech.
- `tags`: string array.
- `required_tags`: string array.
- `optional_tags`: string array.
- `excluded_tags`: string array.
- `trigger`: one of `person_detected`, `person_approaching`, `person_departing`, `interaction`, `idle`, `manual`, `event`, `voice_command`.
- `tone`: e.g. `playful`, `sarcastic`, `friendly`, `flirty`, `absurd`, `deadpan`, `dramatic`, `aggressive_comedy`.
- `intensity`: integer 1–5.
- `audience`: `all_ages` or `adults`.
- `min_age`: 0 for all ages; 18 for adults.
- `weight`: positive number (default 1.0).
- `estimated_quality`: integer 1–10 (your own editorial estimate).
- `requires_response`: boolean.
- `enabled`: true.

Optional: `dialogue` for multi-bird banter using main four ONLY; `trigger_phrases` for Polly voice commands; `conversation` for Polly's separate escalating solo challenges.

Example main-bird entry:
```json
{"id":"A01_jose_hat_0001","family_id":"hat_weather_001","type":"roast","speaker":"jose","text":"That's quite a hat! Does it come with its own weather forecast?","tags":["hat","accessory","fashion"],"required_tags":["hat"],"optional_tags":["bright_clothing"],"excluded_tags":[],"trigger":"person_detected","tone":"playful","intensity":2,"audience":"all_ages","min_age":0,"weight":1.0,"estimated_quality":8,"requires_response":false,"enabled":true}
```
Example Polly entry:
```json
{"id":"P01_polly_fyp_0001","family_id":"polly_barber_001","type":"comeback","speaker":"polly","text":"Fuck you! Your barber didn't give you a haircut, he gave you a fucking warning.","tags":["fuck_you_polly","quick_zinger"],"required_tags":["adult_mode","direct_insult"],"optional_tags":[],"excluded_tags":[],"trigger":"voice_command","trigger_phrases":["fuck you polly","fuck off polly","roast me polly"],"tone":"aggressive_comedy","intensity":4,"audience":"adults","min_age":18,"weight":1.0,"estimated_quality":9,"requires_response":false,"enabled":true}
```
Example four-bird-only banter:
```json
{"id":"A05_banter_0001","family_id":"hat_ship_sails_001","type":"banter","speaker":"jose","text":"Look at that hat! I've seen smaller sails on a pirate ship!","dialogue":[{"speaker":"jose","text":"Look at that hat! I've seen smaller sails on a pirate ship!"},{"speaker":"fritz","text":"And better ones, too!"}],"tags":["hat","pirate","banter"],"required_tags":["hat"],"optional_tags":[],"excluded_tags":[],"trigger":"person_detected","tone":"sarcastic","intensity":2,"audience":"all_ages","min_age":0,"weight":1.0,"estimated_quality":8,"requires_response":false,"enabled":true}
```

## Distribution and editorial review
Target 100 unique items per batch, but return fewer rather than incomplete/invalid JSON or filler. For non-Polly batches: 25% visual/situational, 20% evergreen, 15% interactive, 10% four-main-bird banter, 30% theme-specific. For Polly-only batches: 35% immediate verbal comebacks, 20% clothes/accessories, 15% elaborate absurdity, 10% pirate/tiki trash talk, 10% solo escalation, 10% consenting adult group/unconventional. Preserve assigned theme if it conflicts with these overall proportions.

Before output: mentally check actual comedic payoff, originality, variety, character voice, spoken clarity, schema completeness, ID uniqueness, correct premise-family mapping, consistent observable tags, appropriate adult gating, and strict Polly isolation. Reject weak items. Only output JSON (no fences, preamble or explanations); when near context limit, finish a smaller valid batch.

## Generation assignment (edit these three values each run)
Batch ID: `BATCH_ID`
Primary theme: `BATCH_THEME`
Target chirps: `100`

Suggested batches: A01 fashion/hats, A02 pirates, A03 tiki, A04 general sarcasm, A05 main-four banter, A06 greetings/reactions, A07 family-friendly comedy, A08 special events; P01 Polly challenge comebacks, P02 Polly fashion roasts, P03 elaborate profanity, P04 pirate/tiki adult insults, P05 escalating solo challenges, P06 quick adult zingers.

For P-batches, generate only Polly; for A-batches, never generate Polly. Begin now; output JSON only.
