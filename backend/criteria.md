# Acceptance criteria — FitFindr

Five criteria that say what "working" means for this agent, written in unit 3
**before** any results existed.

An acceptance criterion names a target: a number, a count, a rate, or something
a person could plainly observe. *"The agent handles errors"* is an opinion.
*"When search returns nothing, the agent stops before calling the second tool,
in 5 of 5 tries"* is a criterion.

Under each one, write a sentence or two on **why that target** and not a
stricter one. A reason that says something about your tools, your loop, or the
data earns credit; *"80% seemed reasonable"* does not.

> Missing your own targets next unit costs you nothing. Setting a target so
> easy you can't miss it does.

**Two are written for you. You write three.**

---

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card — in at least 4 of 5 tries.

**Why this target:**
My search is a plain keyword match, so some phrasings will miss, and two of the three tools call a model whose output can vary. I allow one miss.

---

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what to change — 5 of 5 tries.

**Why this target:**
The stop is a plain code check on an empty list before any model call, so it behaves the same every time. Failing it would mean a bug in my branch.

---

## 3. Something about state

Given a query that matches at least one listing, the id in
session["selected_item"] equals the id of the item passed to
suggest_outfit — 5 of 5 tries.

**Why this target:**
this is plain code passing a value, no model involved,
so any mismatch is a bug, not randomness.



---

## 4. Something about the fit card

Given a query that matches at least one listing, the fit card
mentions the item's title, price, and platform — 4 of 5 tries.

**Why this target:**
wording changes every run because a model writes it, and it
sometimes drops a detail, so I allow one miss.

> **Revised in unit 4:** Given a query that matches at least one listing, the fit card names the item recognizably (its category plus at least one other word from its title), its exact price, and its platform — 4 of 5 tries.
>
> **Why revised:** "mentions the item's title" didn't say whether the exact title was required. The same five cards scored 0/5 read strictly and 5/5 read loosely, so the original couldn't be measured. The new version can.


---

## 5. Your choice

Given an empty wardrobe, suggest_outfit returns non-empty styling
advice, not "" or an error — 5 of 5 tries.

**Why this target:**
an empty result breaks user trust, and the empty check is
plain code, so it should never fail.



---

<!-- ─────────────────────────────────────────────────────────────────────────
     UNIT 4 — read this before you change anything above.

     If a criterion turns out to be BROKEN rather than merely unmet, you can
     revise it, and that earns credit. But never delete or edit the original
     line. Add the revision underneath it, like this:

         ## 4. Something about the fit card

         The fit card is different every time.

         **Why this target:** ...

         > **Revised in unit 4:** For 5 different items, the 5 fit cards share
         > no opening sentence.
         >
         > **Why revised:** "different" wasn't checkable — two cards that
         > differed by one word still counted. The new version is something I
         > can actually score.

     That's a revision because the criterion couldn't be MEASURED.

     Lowering a target because you missed it is not a revision, and it costs
     you the point:

         ✗ "I said the empty search stops it 5 of 5 times, but I got 3 of 5,
            so 3 of 5 is more realistic."

     A number you missed stays where it is, gets diagnosed, and gets a fix
     attempted. That's where the points are.
     ───────────────────────────────────────────────────────────────────────── -->
