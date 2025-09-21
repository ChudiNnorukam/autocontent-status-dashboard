"""Build a voice profile from the provided sample posts.

The user supplied a curated set of lessons/tweets. This script treats them as
historical posts, exports them to CSV, and regenerates the voice profile so the
autoposter can base future generations on that tone."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from autoposter.config import get_settings
from autoposter.data_fetcher import TweetSample, export_tweets_to_csv, tweets_to_dataframe
from autoposter.voice_model import build_voice_profile, save_voice_profile


SAMPLE_POSTS = [
    "I built the first version of Feature X blindfolded—no user feedback, no sketches. It shipped. It failed. Lesson: seeing pain before coding saves way more time than tweaking UI.",
    "Spent 3 days designing the “perfect” onboarding flow. Then I realized I didn’t even know what people really meant by “onboarding.” Built a quick sketch, asked. Got clarity.",
    "I launched with 7 features, thinking more = better. User data showed 1 feature got 90% of use. Everything else was noise. Cutting is painful, but necessary.",
    "I delayed product launch for one more week to polish colors. That week cost me traction, learning, feedback. “Ready enough” beats “beautiful but unseen.”",
    "Tried hiring help early for support docs. Butter-smooth, but totally misaligned with what customers asked. Needed to be in the trenches myself first.",
    "Over-estimated what users would “intuitively get.” Spent hours polishing jargon. Turns out I needed to simplify language, not features.",
    "Thought metrics should come first. I built dashboards, kpis, trackers—before defining who the product was for. That was backward.",
    "I built an MVP without talking to anyone. Ship it? Yes. But painful realization: if you don’t know the problem they really have, your “fix” might miss entirely.",
    "Tried to copy successful tools in my niche. Ended up with a weak clone. Originality in solving *your* pain beats replicating someone else’s aesthetic.",
    "I added subscription tiers because “everyone does that.” But customers didn’t need them. Kept packaging simple—less overhead, clearer path.",
    "I thought auto-scaling features were sexy. Spent hours building them. No one used them. Lesson: don’t build for scale before product–market fit.",
    "I ignored feedback that didn’t align with my vision. That almost cost me trust. Lesson: listen, even if you don’t act—people feel heard.",
    "I celebrated my “first 100 users” like a win. But I hadn’t checked churn, engagement. Numbers are lonely without context.",
    "I avoided publishing ugly wireframes because I feared criticism. When I finally shared them, the feedback was gold. Mistake: I bottled up too much polish.",
    "Delayed launch features waiting for “edge cases.” Reality: edge cases are rare early on. Fix core flow first.",
    "Thought marketing was only after product. Started small content, threads, share-backs. That seeded interest before launch.",
    "I misread silence as interest. No messages ≠ people care. Direct asks, surveys, “would you pay for this?” tell more.",
    "I believed “if I build it, they will come.” Nope. I needed to build, then talk to people, then rebuild. Continuous loop, not linear.",
    "I over-trusted coding skills and under-trusted empathy. User interviews taught me more than specs ever did.",
    "Every time I launch, I find 3 things I could’ve trimmed. If you’re not feeling that itch, maybe you built too much.",
    "Thought our feature rollout was complete. Feedback: “I hate the flow.” Fix: I rewrote navigation. Lesson: what feels obvious to you might feel random to others.",
    "I once ignored feedback calling my UI confusing. Bought a theme, restyled everything. But the real fix was simplifying labels & ordering. Lesson: visuals help, but clarity comes from structure.",
    "Built a feature before asking if anyone needed it. Spent days coding. Heard crickets. Fix: I shut it off, asked 10 people. Majority didn’t want it. Lesson: code only what someone needs, not what you imagine.",
    "Feedback said: “Too many steps to get value.” So I flattened user flow. Removed two screens. Lesson: fewer clicks = less drop-off, even if it feels like you’re removing “nice to have.”",
    "Mistake: I measured dozens of metrics. But none were tied to what actually matters: retention & real usage. Fix: trimmed dashboard. Lesson: clarity > noise.",
    "Got feedback that pricing tiers confuse people. Fix: merged two tiers, simplified copy. Lesson: pricing isn’t about showing off value, it's about clarity.",
    "I once trusted “early adopters” feedback too much. They had different priorities. Fix: segmented feedback into “power users vs casual”. Lesson: not all feedback should move roadmap.",
    "Mistake: I built integrations (Slack, email) thinking they were demand. Feedback: “I don’t care.” Removed them. Lesson: enthusiasm ≠ necessity.",
    "I thought expanding platforms (mobile/web) is always a win. Feedback: web version usage dwarfed mobile. Fix: focused web first. Lesson: follow where people actually use, not where you want them to.",
    "Got negative feedback when I skipped onboarding UX. Users thought feature was broken. Fix: added simple guide. Lesson: sometimes “explain what this is” matters more than shiny visuals.",
    "I released a “complete” product version with all planned features. Feedback: overwhelming. Fix: rolled back some toggles. Lesson: cutting is essential—even if it hurts.",
    "Thought bugs were minor annoyances. After feedback, realized some broke trust. Fix: prioritized bug fixes over “new features” for a sprint. Lesson: trust = consistency.",
    "Mistake: I ignored accessibility feedback (“text too small”, “color contrast off”). Fix: updated font sizes, palettes. Lesson: small design touches matter for many more people than you think.",
    "Built with my own jargon. Feedback: people didn’t understand terms. Fix: rewrote copy in plain English. Lesson: you think clearer than most.",
    "Feedback: “Hard to find the thing I paid for.” Mistake: pricing page, documentation, features buried. Fix: reorganized menu, added dashboard shortcut. Lesson: make what matters visible.",
    "Mistake: I promised roadmap publicly. Feedback: frustrations when dates slipped. Fix: switched to “what we’re exploring”, not “what we’ll ship”. Lesson: under-promise, over-deliver.",
    "Received feedback: “You’re missing edge cases,” but users only deal with core flows. Mistake: building for edge too early. Fix: paused extras. Lesson: core > completeness.",
    "I once delayed feature X because I thought I didn’t have capacity. Feedback: users commented “we need this.” Fix: simplified scope, shipped minimal version. Lesson: imperfect > invisible.",
    "Mistake: didn’t prioritize customer success. Feedback: people got stuck onboarding, support requests ballooned. Fix: built docs + videos. Lesson: easing the way matters more than building more.",
    "Thought marketing = post-launch. Feedback: people didn’t know anything existed. Fix: started teasing early, build-public threads. Lesson: marketing is part of the build.",
    "Got feedback that sending too many emails annoyed users. Mistake: overloaded sequences. Fix: reduced frequency. Lesson: attention and respect are currencies.",
    "I once added feature toggle settings because I thought users wanted control. Feedback: settings cluttered UX. Fix: hide advanced options. Lesson: default paths are powerful.",
    "Mistake: ignored competitor’s pricing & positioning. Feedback: customers compared me to them—and often chose them. Fix: adjusted pricing and messaging. Lesson: ignorance of alternatives is expensive.",
    "Built a beautiful landing page. Feedback: the copy didn't explain value. Visitors bounced. Fix: rewrite focus on problem + outcome. Lesson: design draws them in; copy keeps them.",
    "I assumed scaling the user base was the goal. Feedback: many users signed up, few stayed. Fix: focus on retention, not just acquisition. Lesson: growth without stickiness drains resources.",
    "Mistake: not collecting testimonials or feedback early. Feedback: when we asked later, people had forgotten their experience. Fix: prompt at moment of delight. Lesson: feedback windows are small.",
    "Ignored negative feedback because it felt harsh. But that feedback showed patterns. Fix: built tracking of complaints. Lesson: what you avoid hearing often holds the keys to improvement.",
    "Tried to optimize for conversion on landing page before verifying core idea. Feedback: people didn’t care about the features listed. Fix: test headline + problem statement first. Lesson: resonate first, persuade second.",
    "Mistake: built a feature that solved my problem, not theirs. Feedback: people said “this isn’t for me.” Fix: pivoted to adjust for issues they actually had. Lesson: empathy over ego’s assumptions.",
    "Thought fast growth meant success. Feedback: features got messy, customer support lagged. Fix: slowed down feature rollout, invested in quality. Lesson: sustainable velocity beats flashy sprint.",
]


def main() -> None:
    settings = get_settings()

    base_date = datetime.now()
    tweets: list[TweetSample] = []
    for idx, text in enumerate(SAMPLE_POSTS, start=1):
        tweets.append(
            TweetSample(
                id=idx,
                date=base_date - timedelta(days=len(SAMPLE_POSTS) - idx),
                content=text,
                like_count=0,
                reply_count=0,
                retweet_count=0,
                url=f"https://twitter.com/{settings.username}/status/{1000 + idx}",
                is_retweet=False,
                is_reply=False,
            )
        )

    export_path = Path(settings.data_dir) / f"{settings.username}_sample_posts.csv"
    export_tweets_to_csv(tweets, export_path)

    df = tweets_to_dataframe(tweets)
    profile = build_voice_profile(df)
    profile.summary = (
        "Reflective builder voice focused on product clarity, customer feedback, and "
        "shipping lean iterations. Emphasizes learning from mistakes, simplifying "
        "flows, and balancing build-in-public marketing with user empathy."
    )
    profile.hashtags = [
        "buildinpublic",
        "productstrategy",
        "customerfeedback",
        "startups",
        "shipfast",
    ]
    profile.mentions = [
        "founders",
        "customers",
        "designers",
        "productteams",
        "builders",
    ]
    profile.emoji = [":hammer:", ":rocket:", ":memo:", ":repeat:", ":bulb:"]
    save_voice_profile(profile, settings.voice_profile_path)

    print(f"Sample tweets saved to {export_path}")
    print("Voice profile updated at", settings.voice_profile_path)
    print("Summary preview:", profile.summary)


if __name__ == "__main__":
    main()
