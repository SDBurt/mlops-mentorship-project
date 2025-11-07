-- ============================================================================
-- Custom Macros for Reddit Data Transformations
-- ============================================================================
-- These macros encapsulate business logic for reuse across models.
-- Making it easier to maintain and update logic in one place.
-- ============================================================================

{% macro reputation_tier(reputation_score_column) %}
    CASE
        WHEN {{ reputation_score_column }} >= 10000 THEN 'Elite'
        WHEN {{ reputation_score_column }} >= 5000 THEN 'High'
        WHEN {{ reputation_score_column }} >= 1000 THEN 'Medium'
        WHEN {{ reputation_score_column }} >= 100 THEN 'Low'
        ELSE 'New'
    END
{% endmacro %}

{% macro activity_type(total_posts_column, total_comments_column) %}
    CASE
        WHEN {{ total_posts_column }} > {{ total_comments_column }} THEN 'Poster'
        WHEN {{ total_comments_column }} > {{ total_posts_column }} THEN 'Commenter'
        WHEN {{ total_posts_column }} = {{ total_comments_column }} AND {{ total_posts_column }} > 0 THEN 'Balanced'
        ELSE 'Unknown'
    END
{% endmacro %}

{% macro engagement_score(score_col, num_comments_col, total_awards_col) %}
    ({{ score_col }} * 0.5) +
    ({{ num_comments_col }} * 1.5) +
    (COALESCE({{ total_awards_col }}, 0) * 20)
{% endmacro %}

{% macro content_type(is_self_col, is_video_col, is_gallery_col, url_col) %}
    CASE
        WHEN {{ is_self_col }} THEN 'self'
        WHEN {{ is_video_col }} THEN 'video'
        WHEN {{ is_gallery_col }} THEN 'gallery'
        WHEN {{ url_col }} IS NOT NULL AND {{ url_col }} != '' THEN 'link'
        ELSE 'other'
    END
{% endmacro %}
