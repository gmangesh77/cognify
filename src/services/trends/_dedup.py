from difflib import SequenceMatcher

from src.services.trends.reddit_client import RedditPostResponse


def deduplicate_crossposts(
    posts: list[RedditPostResponse],
) -> tuple[list[RedditPostResponse], int]:
    """Two-pass dedup: crosspost_parent IDs then fuzzy title match.
    Returns (deduped_posts, removed_count)."""
    if not posts:
        return [], 0

    # Pass 1: group by crosspost_parent
    parent_groups: dict[str, list[RedditPostResponse]] = {}
    no_parent: list[RedditPostResponse] = []
    for post in posts:
        parent = post["crosspost_parent"]
        if parent:
            parent_groups.setdefault(parent, []).append(post)
        else:
            no_parent.append(post)

    # Keep highest score per parent group
    survivors: list[RedditPostResponse] = []
    for group in parent_groups.values():
        best = max(group, key=lambda p: p["score"])
        survivors.append(best)

    # Pass 2: fuzzy title match on remaining posts
    merged_into: dict[int, int] = {}  # index -> group leader index
    for i, post_a in enumerate(no_parent):
        if i in merged_into:
            continue
        for j in range(i + 1, len(no_parent)):
            if j in merged_into:
                continue
            ratio = SequenceMatcher(
                None,
                post_a["title"].lower(),
                no_parent[j]["title"].lower(),
            ).ratio()
            if ratio > 0.85:
                merged_into[j] = i

    # Build fuzzy groups
    fuzzy_groups: dict[int, list[int]] = {}
    for j, leader in merged_into.items():
        fuzzy_groups.setdefault(leader, [leader]).append(j)

    # Keep highest score per fuzzy group
    for i, post in enumerate(no_parent):
        if i in merged_into:
            continue
        if i in fuzzy_groups:
            group_indices = fuzzy_groups[i]
            group_posts = [no_parent[idx] for idx in group_indices]
            best = max(group_posts, key=lambda p: p["score"])
            survivors.append(best)
        else:
            survivors.append(post)

    original_count = len(posts)
    removed = original_count - len(survivors)
    return survivors, removed
