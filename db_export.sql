--
-- PostgreSQL database dump
--

\restrict DDIoN2yKfb7Jy5JlgvL6towggaMQRXgEEAi68br3dMcteVErxdT6tvDJRzREBs0

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: reset_ids(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reset_ids(target_table text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    new_max_id INTEGER;
BEGIN
    EXECUTE format('
        CREATE TEMP TABLE temp_sync AS SELECT * FROM public.%I ORDER BY id;
        TRUNCATE public.%I RESTART IDENTITY CASCADE;
        INSERT INTO public.%I (store_id, affiliate_link, public_coupon, extra_offer, store_bio, priority_score, discount_value, store_tags, my_coupon, first_time, last_time, total_link_clicks, total_coupon_copies, total_search_hits, performance_status) 
        SELECT store_id, affiliate_link, public_coupon, extra_offer, store_bio, priority_score, discount_value, store_tags, my_coupon, first_time, last_time, total_link_clicks, total_coupon_copies, total_search_hits, performance_status FROM temp_sync;
        DROP TABLE temp_sync;
    ', target_table, target_table, target_table);
    
    -- تحديث العداد التلقائي ليبدأ من الرقم التالي الصحيح
    EXECUTE format('SELECT MAX(id) FROM public.%I', target_table) INTO new_max_id;
    IF new_max_id IS NULL THEN new_max_id := 0; END IF;
    EXECUTE format('SELECT setval(pg_get_serial_sequence(''public.%I'', ''id''), %s)', target_table, COALESCE(new_max_id, 0) + 1, false);
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: action_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.action_logs (
    id integer NOT NULL,
    store_id text,
    action_type text,
    details text,
    action_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    user_id bigint
);


--
-- Name: action_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.action_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: action_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.action_logs_id_seq OWNED BY public.action_logs.id;


--
-- Name: api_partners; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_partners (
    partner_id integer NOT NULL,
    partner_name text NOT NULL,
    api_endpoint text,
    usage_limit integer,
    status text DEFAULT 'نشط'::text,
    api_key text,
    api_secret text,
    extra_headers jsonb
);


--
-- Name: api_partners_partner_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.api_partners_partner_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_partners_partner_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_partners_partner_id_seq OWNED BY public.api_partners.partner_id;


--
-- Name: app_monitor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_monitor (
    log_id integer NOT NULL,
    log_type text,
    action_details text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: app_monitor_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.app_monitor_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: app_monitor_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.app_monitor_log_id_seq OWNED BY public.app_monitor.log_id;


--
-- Name: auto_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auto_rules (
    rule_id integer NOT NULL,
    rule_name text,
    is_active boolean DEFAULT false,
    settings jsonb,
    last_run timestamp without time zone
);


--
-- Name: auto_rules_rule_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auto_rules_rule_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auto_rules_rule_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auto_rules_rule_id_seq OWNED BY public.auto_rules.rule_id;


--
-- Name: available_channels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.available_channels (
    channel_id integer NOT NULL,
    channel_name text NOT NULL,
    telegram_id text NOT NULL,
    is_active boolean DEFAULT true
);


--
-- Name: available_channels_channel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.available_channels_channel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: available_channels_channel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.available_channels_channel_id_seq OWNED BY public.available_channels.channel_id;


--
-- Name: bot_dynamic_buttons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_dynamic_buttons (
    button_id integer NOT NULL,
    button_text text NOT NULL,
    button_callback text NOT NULL,
    is_active boolean DEFAULT true,
    display_order integer DEFAULT 0
);


--
-- Name: bot_dynamic_buttons_button_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bot_dynamic_buttons_button_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bot_dynamic_buttons_button_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bot_dynamic_buttons_button_id_seq OWNED BY public.bot_dynamic_buttons.button_id;


--
-- Name: bot_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bot_users (
    telegram_id bigint NOT NULL,
    username text,
    joined_at timestamp without time zone DEFAULT now(),
    last_seen timestamp without time zone,
    fav_store_inferred text,
    store_copy_count integer DEFAULT 0,
    fav_tag_inferred text,
    tag_visit_count integer DEFAULT 0,
    user_status text,
    visited_clicks integer DEFAULT 0,
    country text,
    city text,
    device_type text,
    search_date_timestamp timestamp without time zone,
    manual_favorites text[],
    copied_coupons_history text[],
    interests text[],
    marketing_segment text,
    spy_behavior_logs jsonb,
    spy_behavior jsonb,
    loyalty_rank text,
    lang text DEFAULT 'ar'::text,
    name_en text
);


--
-- Name: broadcast_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.broadcast_logs (
    id integer NOT NULL,
    message_text text,
    image_url text,
    target_audience text,
    sent_by text,
    sent_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    delivery_count integer DEFAULT 0
);


--
-- Name: broadcast_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.broadcast_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: broadcast_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.broadcast_logs_id_seq OWNED BY public.broadcast_logs.id;


--
-- Name: categories_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories_tags (
    id integer NOT NULL,
    tag_name character varying(100) NOT NULL,
    priority_score integer DEFAULT 0,
    visit_count integer DEFAULT 0,
    total_interactions integer DEFAULT 0,
    is_trending character varying(50) DEFAULT 'عادي'::character varying,
    click_count integer DEFAULT 0,
    "Tag_clicks" integer DEFAULT 0
);


--
-- Name: categories_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categories_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categories_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categories_tags_id_seq OWNED BY public.categories_tags.id;


--
-- Name: channel_ads_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.channel_ads_queue (
    ad_id integer NOT NULL,
    ad_title text NOT NULL,
    ad_link text NOT NULL,
    ad_category text,
    ad_coupon text,
    ad_note text,
    scheduled_time timestamp without time zone,
    status text DEFAULT 'مجدول ⏳'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    target_channel text DEFAULT 'القناة العامة 📢'::text
);


--
-- Name: channel_ads_queue_ad_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.channel_ads_queue_ad_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: channel_ads_queue_ad_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.channel_ads_queue_ad_id_seq OWNED BY public.channel_ads_queue.ad_id;


--
-- Name: competitor_watch; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.competitor_watch (
    id integer NOT NULL,
    store_name text,
    last_code text,
    status text DEFAULT 'مستقر'::text,
    discount_rate integer
);


--
-- Name: competitor_watch_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.competitor_watch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: competitor_watch_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.competitor_watch_id_seq OWNED BY public.competitor_watch.id;


--
-- Name: content_studio_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.content_studio_logs (
    id integer NOT NULL,
    product_name text,
    platform text,
    ad_text text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    bg_color text,
    text_color text
);


--
-- Name: content_studio_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.content_studio_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: content_studio_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.content_studio_logs_id_seq OWNED BY public.content_studio_logs.id;


--
-- Name: master; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.master (
    id integer NOT NULL,
    store_id text,
    affiliate_link text,
    public_coupon text,
    extra_offer text,
    store_bio text,
    priority_score text DEFAULT 0,
    discount_value text,
    store_tags text,
    my_coupon text,
    first_time date DEFAULT CURRENT_DATE,
    last_time date,
    total_link_clicks integer DEFAULT 0,
    total_coupon_copies integer DEFAULT 0,
    total_search_hits integer DEFAULT 0,
    performance_status text DEFAULT 'معتدل'::text,
    visit_categorie integer DEFAULT 0,
    target_category text,
    total_clicks integer DEFAULT 0,
    is_trending character varying(50) DEFAULT 'عادي'::character varying,
    click_count integer DEFAULT 0,
    copy_clicks integer DEFAULT 0,
    link_clicks integer DEFAULT 0,
    name_en text
);


--
-- Name: coupons_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.coupons_view AS
 SELECT id,
    store_id,
    affiliate_link,
    public_coupon,
    extra_offer,
    store_bio,
    priority_score,
    discount_value,
    store_tags,
    my_coupon,
    first_time,
    last_time,
    total_link_clicks,
    total_coupon_copies,
    total_search_hits,
    performance_status,
    visit_categorie,
    target_category,
    total_clicks
   FROM public.master;


--
-- Name: direct_search; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.direct_search (
    id integer NOT NULL,
    search_keyword text,
    store_id text,
    search_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    user_found boolean,
    platform text DEFAULT 'Dashboard'::text,
    name_en text
);


--
-- Name: direct_search_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.direct_search_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: direct_search_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.direct_search_id_seq OWNED BY public.direct_search.id;


--
-- Name: flash_offers_queue; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.flash_offers_queue (
    offer_id integer NOT NULL,
    offer_title text NOT NULL,
    reward_points integer,
    duration_minutes integer,
    target_coupon text,
    status text DEFAULT 'نشط 🔥'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: flash_offers_queue_offer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.flash_offers_queue_offer_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: flash_offers_queue_offer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.flash_offers_queue_offer_id_seq OWNED BY public.flash_offers_queue.offer_id;


--
-- Name: franchise_agents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.franchise_agents (
    agent_id integer NOT NULL,
    agent_name text NOT NULL,
    region text,
    profit_share double precision,
    join_date date DEFAULT CURRENT_DATE
);


--
-- Name: franchise_agents_agent_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.franchise_agents_agent_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: franchise_agents_agent_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.franchise_agents_agent_id_seq OWNED BY public.franchise_agents.agent_id;


--
-- Name: invoice_verifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_verifications (
    invoice_id integer NOT NULL,
    user_handle text,
    status text DEFAULT 'قيد الانتظار ⏳'::text
);


--
-- Name: invoice_verifications_invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoice_verifications_invoice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoice_verifications_invoice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoice_verifications_invoice_id_seq OWNED BY public.invoice_verifications.invoice_id;


--
-- Name: loyalty_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loyalty_history (
    id integer NOT NULL,
    user_id bigint,
    action_type text,
    points_earned integer,
    log_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: loyalty_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.loyalty_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: loyalty_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.loyalty_history_id_seq OWNED BY public.loyalty_history.id;


--
-- Name: loyalty_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.loyalty_settings (
    setting_key text NOT NULL,
    setting_value integer
);


--
-- Name: master_input_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.master_input_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: master_input_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.master_input_id_seq OWNED BY public.master.id;


--
-- Name: prediction_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prediction_logs (
    id integer NOT NULL,
    search_hour integer,
    search_count integer DEFAULT 1,
    store_name text,
    log_date date DEFAULT CURRENT_DATE
);


--
-- Name: prediction_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.prediction_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: prediction_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.prediction_logs_id_seq OWNED BY public.prediction_logs.id;


--
-- Name: product_comparisons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_comparisons (
    id integer NOT NULL,
    store_id text NOT NULL,
    product_name text,
    price text,
    affiliate_link text,
    public_coupon text,
    discount_value text,
    extra_offer text,
    priority_score integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    store_name text
);


--
-- Name: product_comparisons_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_comparisons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_comparisons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_comparisons_id_seq OWNED BY public.product_comparisons.id;


--
-- Name: search_analytics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_analytics (
    id integer NOT NULL,
    search_query text,
    search_count integer DEFAULT 1,
    last_searched timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    name_en text
);


--
-- Name: search_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.search_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: search_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.search_analytics_id_seq OWNED BY public.search_analytics.id;


--
-- Name: seasonal_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seasonal_events (
    event_id integer NOT NULL,
    event_name text NOT NULL,
    event_date text,
    bot_status text DEFAULT 'انتظار'::text,
    ai_suggestion text,
    emotional_tip text
);


--
-- Name: seasonal_events_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seasonal_events_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seasonal_events_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seasonal_events_event_id_seq OWNED BY public.seasonal_events.event_id;


--
-- Name: security_blacklist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_blacklist (
    block_id integer NOT NULL,
    target_value text NOT NULL,
    reason text,
    block_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: security_blacklist_block_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.security_blacklist_block_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: security_blacklist_block_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.security_blacklist_block_id_seq OWNED BY public.security_blacklist.block_id;


--
-- Name: security_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_settings (
    setting_key text NOT NULL,
    setting_value integer
);


--
-- Name: security_threats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_threats (
    threat_id integer NOT NULL,
    threat_type text,
    source_val text,
    action_taken text,
    detection_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: security_threats_threat_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.security_threats_threat_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: security_threats_threat_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.security_threats_threat_id_seq OWNED BY public.security_threats.threat_id;


--
-- Name: sent_coupon_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sent_coupon_messages (
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    store_id text NOT NULL,
    user_id bigint,
    sent_at timestamp without time zone DEFAULT now(),
    name_en text
);


--
-- Name: support_tickets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.support_tickets (
    id integer NOT NULL,
    username text,
    telegram_id bigint,
    message text,
    status text DEFAULT 'open'::text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: support_tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.support_tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: support_tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.support_tickets_id_seq OWNED BY public.support_tickets.id;


--
-- Name: traffic_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.traffic_sources (
    id integer NOT NULL,
    source_name text,
    visit_count integer DEFAULT 0
);


--
-- Name: traffic_sources_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.traffic_sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: traffic_sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.traffic_sources_id_seq OWNED BY public.traffic_sources.id;


--
-- Name: unavailable_codes_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unavailable_codes_requests (
    id integer NOT NULL,
    user_id bigint,
    brand_name text,
    requested_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    user_email text,
    master_id integer,
    name_en text
);


--
-- Name: unavailable_codes_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unavailable_codes_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unavailable_codes_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unavailable_codes_requests_id_seq OWNED BY public.unavailable_codes_requests.id;


--
-- Name: user_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_preferences (
    user_id bigint NOT NULL,
    preferred_categories text[],
    location_city text,
    last_targeted_broadcast timestamp without time zone,
    opt_in_notifications boolean DEFAULT true
);


--
-- Name: users_master; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users_master (
    user_id bigint NOT NULL,
    username text,
    points integer DEFAULT 0,
    rank text,
    main_interest text,
    loyalty_score integer,
    total_savings double precision DEFAULT 0,
    last_active timestamp without time zone,
    birth_date date,
    favorite_brands text[],
    meta_data jsonb,
    name_en text
);


--
-- Name: action_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_logs ALTER COLUMN id SET DEFAULT nextval('public.action_logs_id_seq'::regclass);


--
-- Name: api_partners partner_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_partners ALTER COLUMN partner_id SET DEFAULT nextval('public.api_partners_partner_id_seq'::regclass);


--
-- Name: app_monitor log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_monitor ALTER COLUMN log_id SET DEFAULT nextval('public.app_monitor_log_id_seq'::regclass);


--
-- Name: auto_rules rule_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auto_rules ALTER COLUMN rule_id SET DEFAULT nextval('public.auto_rules_rule_id_seq'::regclass);


--
-- Name: available_channels channel_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.available_channels ALTER COLUMN channel_id SET DEFAULT nextval('public.available_channels_channel_id_seq'::regclass);


--
-- Name: bot_dynamic_buttons button_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_dynamic_buttons ALTER COLUMN button_id SET DEFAULT nextval('public.bot_dynamic_buttons_button_id_seq'::regclass);


--
-- Name: broadcast_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broadcast_logs ALTER COLUMN id SET DEFAULT nextval('public.broadcast_logs_id_seq'::regclass);


--
-- Name: categories_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories_tags ALTER COLUMN id SET DEFAULT nextval('public.categories_tags_id_seq'::regclass);


--
-- Name: channel_ads_queue ad_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_ads_queue ALTER COLUMN ad_id SET DEFAULT nextval('public.channel_ads_queue_ad_id_seq'::regclass);


--
-- Name: competitor_watch id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.competitor_watch ALTER COLUMN id SET DEFAULT nextval('public.competitor_watch_id_seq'::regclass);


--
-- Name: content_studio_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_studio_logs ALTER COLUMN id SET DEFAULT nextval('public.content_studio_logs_id_seq'::regclass);


--
-- Name: direct_search id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.direct_search ALTER COLUMN id SET DEFAULT nextval('public.direct_search_id_seq'::regclass);


--
-- Name: flash_offers_queue offer_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flash_offers_queue ALTER COLUMN offer_id SET DEFAULT nextval('public.flash_offers_queue_offer_id_seq'::regclass);


--
-- Name: franchise_agents agent_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.franchise_agents ALTER COLUMN agent_id SET DEFAULT nextval('public.franchise_agents_agent_id_seq'::regclass);


--
-- Name: invoice_verifications invoice_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_verifications ALTER COLUMN invoice_id SET DEFAULT nextval('public.invoice_verifications_invoice_id_seq'::regclass);


--
-- Name: loyalty_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loyalty_history ALTER COLUMN id SET DEFAULT nextval('public.loyalty_history_id_seq'::regclass);


--
-- Name: master id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master ALTER COLUMN id SET DEFAULT nextval('public.master_input_id_seq'::regclass);


--
-- Name: prediction_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediction_logs ALTER COLUMN id SET DEFAULT nextval('public.prediction_logs_id_seq'::regclass);


--
-- Name: product_comparisons id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_comparisons ALTER COLUMN id SET DEFAULT nextval('public.product_comparisons_id_seq'::regclass);


--
-- Name: search_analytics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_analytics ALTER COLUMN id SET DEFAULT nextval('public.search_analytics_id_seq'::regclass);


--
-- Name: seasonal_events event_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seasonal_events ALTER COLUMN event_id SET DEFAULT nextval('public.seasonal_events_event_id_seq'::regclass);


--
-- Name: security_blacklist block_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_blacklist ALTER COLUMN block_id SET DEFAULT nextval('public.security_blacklist_block_id_seq'::regclass);


--
-- Name: security_threats threat_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_threats ALTER COLUMN threat_id SET DEFAULT nextval('public.security_threats_threat_id_seq'::regclass);


--
-- Name: support_tickets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets ALTER COLUMN id SET DEFAULT nextval('public.support_tickets_id_seq'::regclass);


--
-- Name: traffic_sources id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.traffic_sources ALTER COLUMN id SET DEFAULT nextval('public.traffic_sources_id_seq'::regclass);


--
-- Name: unavailable_codes_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unavailable_codes_requests ALTER COLUMN id SET DEFAULT nextval('public.unavailable_codes_requests_id_seq'::regclass);


--
-- Data for Name: action_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.action_logs (id, store_id, action_type, details, action_time, user_id) FROM stdin;
1	\N	start	user:650035493	2026-05-01 16:44:16.44017	650035493
2	\N	view_all	user:650035493	2026-05-01 16:44:29.906109	650035493
3	\N	view_sections	user:650035493	2026-05-01 16:45:03.007845	650035493
4	\N	end_session	user:650035493	2026-05-01 16:45:08.112533	650035493
5	\N	start	user:650035493	2026-05-01 17:11:08.112222	650035493
6	\N	view_all	user:650035493	2026-05-01 17:11:11.137257	650035493
7	\N	view_sections	user:650035493	2026-05-01 17:11:20.710574	650035493
8	\N	view_tag	user:650035493;tag:ازياء	2026-05-01 17:11:25.815884	650035493
9	\N	view_tag	user:650035493;tag:أزياء	2026-05-01 17:11:30.356249	650035493
10	\N	view_tag	user:650035493;tag:إلكترونيات	2026-05-01 17:11:38.683661	650035493
11	\N	view_tag	user:650035493;tag:قهوة	2026-05-01 17:11:42.953474	650035493
12	\N	back	user:650035493	2026-05-01 17:11:46.997266	650035493
13	\N	search	keyword:ترند2;found:True;user:650035493	2026-05-01 17:11:59.473062	650035493
14	\N	request_code	user:650035493;brand:➕ طلب كود	2026-05-01 17:12:21.698375	650035493
15	\N	request_code	user:650035493;brand:نون	2026-05-01 17:12:31.596006	650035493
16	\N	end_session	user:650035493	2026-05-01 17:12:35.83103	650035493
17	\N	start	\N	2026-05-01 19:20:11.666198	650035493
18	\N	start	\N	2026-05-01 19:20:11.674049	650035493
19	\N	idle_alert	\N	2026-05-01 19:20:12.075929	650035493
20	\N	start	\N	2026-05-01 19:20:14.096986	650035493
21	\N	end_session	\N	2026-05-01 19:20:31.790139	650035493
22	\N	unknown_input	text:h	2026-05-01 19:20:45.794925	650035493
23	\N	view_all	\N	2026-05-01 19:20:53.916945	650035493
24	\N	unknown_input	text:g	2026-05-01 19:21:30.836279	650035493
25	\N	request_code	brand:نون	2026-05-01 19:21:52.501092	650035493
26	\N	unknown_input	text:ت	2026-05-01 19:22:10.397987	650035493
27	\N	request_code	brand:نون	2026-05-01 19:22:14.97166	650035493
28	\N	unknown_input	text:ع	2026-05-01 19:22:51.575921	650035493
29	\N	search	keyword:نون;found:True	2026-05-01 19:23:00.113994	650035493
30	\N	unknown_input	text:و	2026-05-01 19:24:11.01724	650035493
31	\N	unknown_input	text:ا	2026-05-01 19:24:11.017342	650035493
32	\N	view_sections	\N	2026-05-01 19:24:13.666185	650035493
33	\N	unknown_input	text:وش	2026-05-01 19:24:13.665669	650035493
34	\N	view_all	\N	2026-05-01 19:24:14.080411	650035493
35	\N	end_session	\N	2026-05-01 19:24:14.324515	650035493
36	\N	unknown_input	text:و	2026-05-01 19:24:22.152109	650035493
37	\N	view_sections	\N	2026-05-01 19:24:33.140411	650035493
38	\N	view_tag	tag:أزياء	2026-05-01 19:24:37.217985	650035493
39	\N	view_tag	tag:ازياء	2026-05-01 19:25:00.267186	650035493
40	\N	view_tag	tag:أزياء	2026-05-01 19:25:02.948089	650035493
41	\N	back	\N	2026-05-01 19:25:29.089683	650035493
42	\N	search	keyword:ازياء;found:True	2026-05-01 19:25:36.124619	650035493
43	\N	view_sections	\N	2026-05-01 19:25:49.548511	650035493
44	\N	view_tag	tag:أطفال	2026-05-01 19:25:52.74828	650035493
45	\N	back	\N	2026-05-01 19:26:03.408182	650035493
46	\N	back	\N	2026-05-01 19:26:03.832858	650035493
47	\N	view_sections	\N	2026-05-01 19:26:05.6292	650035493
48	\N	view_tag	tag:تجميل	2026-05-01 19:26:06.749433	650035493
49	\N	back	\N	2026-05-01 19:26:07.999328	650035493
50	\N	back	\N	2026-05-01 19:26:08.44424	650035493
51	\N	back	\N	2026-05-01 19:26:08.695105	650035493
52	\N	end_session	\N	2026-05-01 19:26:08.889635	650035493
53	\N	start	\N	2026-05-01 19:26:14.025475	650035493
54	\N	request_code	brand:فراس	2026-05-01 19:26:20.621901	650035493
55	\N	search	keyword:اطفال;found:False	2026-05-01 19:26:29.521681	650035493
56	\N	unknown_input	text:نون	2026-05-01 19:26:46.047317	650035493
57	\N	search	keyword:نون;found:True	2026-05-01 19:27:02.059764	650035493
58	نون جديد	click_link	\N	2026-05-01 19:28:24.409752	650035493
59	\N	idle_alert	\N	2026-05-01 19:42:13.110613	650035493
60	\N	idle_alert	\N	2026-05-02 15:37:41.522612	650035493
61	نون11111	copy_coupon	\N	2026-05-02 15:37:52.877988	650035493
62	\N	start	\N	2026-05-02 15:38:06.007298	650035493
63	\N	view_all	\N	2026-05-02 15:38:08.083836	650035493
64	\N	view_sections	\N	2026-05-02 15:38:23.888399	650035493
65	\N	view_tag	tag:أزياء	2026-05-02 15:38:26.138805	650035493
66	\N	back	\N	2026-05-02 15:38:34.009627	650035493
67	\N	idle_alert	\N	2026-05-02 15:53:44.979929	650035493
68	\N	end_session	\N	2026-05-02 15:54:09.658744	650035493
69	\N	start	\N	2026-05-02 16:45:29.552419	650035493
70	\N	idle_alert	\N	2026-05-02 16:45:29.594003	650035493
71	\N	start	\N	2026-05-02 16:45:46.47177	650035493
72	\N	view_all	\N	2026-05-02 16:45:49.129353	650035493
73	نون11111	click_link	\N	2026-05-02 16:45:52.961584	650035493
74	1	click_link	\N	2026-05-02 16:45:56.502352	650035493
75	3	copy_coupon	\N	2026-05-02 16:45:59.112885	650035493
76	2	copy_coupon	\N	2026-05-02 16:46:09.425744	650035493
77	1	click_link	\N	2026-05-02 16:46:27.513926	650035493
78	ترند2	click_link	\N	2026-05-02 16:46:31.378761	650035493
79	ترند2	click_link	\N	2026-05-02 16:46:34.591444	650035493
80	2	click_link	\N	2026-05-02 16:46:36.261146	650035493
81	\N	idle_alert	\N	2026-05-02 17:05:09.309915	650035493
82	\N	idle_alert	\N	2026-05-02 17:07:05.405044	650035493
83	\N	idle_alert	\N	2026-05-02 17:12:21.136987	650035493
84	\N	idle_alert	\N	2026-05-02 18:45:13.19084	650035493
85	\N	start	\N	2026-05-02 18:46:10.980331	650035493
86	\N	lang_pick	code:ar_sa	2026-05-02 18:46:16.305673	650035493
87	\N	view_all	\N	2026-05-02 18:48:23.196173	650035493
88	نون جديد	reaction_heart	\N	2026-05-02 18:48:39.630085	650035493
89	\N	view_sections	\N	2026-05-02 18:48:44.628373	650035493
90	\N	view_tag	tag:اكسسوارات	2026-05-02 18:48:47.816071	650035493
91	كلود1	click_link	\N	2026-05-02 18:48:53.21313	650035493
92	كلود1	copy_coupon	\N	2026-05-02 18:48:55.456005	650035493
93	\N	back	\N	2026-05-02 18:49:24.589971	650035493
94	\N	end_session	\N	2026-05-02 18:49:37.279677	650035493
95	\N	idle_alert	\N	2026-05-02 19:05:17.79784	650035493
96	\N	start	\N	2026-05-02 22:44:17.081598	650035493
97	\N	start	\N	2026-05-02 22:45:01.286807	650035493
98	\N	view_all	\N	2026-05-02 22:45:08.621257	650035493
99	\N	end_session	\N	2026-05-02 22:46:45.083157	650035493
100	\N	start	\N	2026-05-02 22:46:47.6947	650035493
101	\N	view_all	\N	2026-05-02 22:47:53.743664	650035493
102	\N	end_session	\N	2026-05-02 22:56:01.584676	650035493
103	\N	idle_alert	\N	2026-05-02 23:22:44.202144	650035493
104	\N	start	\N	2026-05-02 23:28:27.214079	891358114
105	\N	lang_pick	code:ar_sa;device:Android	2026-05-02 23:29:21.63086	891358114
106	\N	request_code	brand:🛑 إنهاء	2026-05-02 23:30:50.888799	891358114
107	\N	start	\N	2026-05-02 23:32:52.757285	894158532
108	\N	lang_pick	code:ar_sa;device:Android	2026-05-02 23:32:54.718916	894158532
109	\N	view_sections	\N	2026-05-02 23:32:57.150351	894158532
110	\N	request_code	brand:🏷️ أزياء	2026-05-02 23:32:59.37847	894158532
111	\N	view_all	\N	2026-05-02 23:33:03.907708	894158532
112	نون50	copy_coupon	\N	2026-05-02 23:33:09.527804	894158532
113	نون50	copy_coupon	\N	2026-05-02 23:33:10.562438	894158532
114	\N	end_session	\N	2026-05-02 23:40:42.018216	894158532
115	\N	start	\N	2026-05-02 23:40:44.804397	894158532
116	\N	view_sections	\N	2026-05-02 23:40:49.006619	894158532
117	\N	view_tag	tag:رقمي	2026-05-02 23:40:53.72221	894158532
118	شاهد	copy_coupon	\N	2026-05-02 23:40:58.034269	894158532
119	شاهد	click_link	\N	2026-05-02 23:40:58.945714	894158532
120	\N	start	\N	2026-05-02 23:41:39.090993	872962302
121	\N	lang_pick	code:ar_sa;device:Android	2026-05-02 23:41:42.240616	872962302
122	\N	view_sections	\N	2026-05-02 23:41:46.96953	872962302
123	\N	view_tag	tag:أطفال	2026-05-02 23:42:02.010748	872962302
124	\N	view_tag	tag:اكسسوارات	2026-05-02 23:42:12.402556	872962302
125	\N	view_tag	tag:ازياء	2026-05-02 23:42:16.155795	872962302
126	\N	back	\N	2026-05-02 23:42:17.710686	894158532
127	\N	view_tag	tag:أزياء	2026-05-02 23:42:19.121743	872962302
128	\N	view_tag	tag:الكترونيات	2026-05-02 23:42:24.26661	872962302
129	\N	view_tag	tag:رقمي	2026-05-02 23:42:28.01877	872962302
130	\N	view_tag	tag:سفر	2026-05-02 23:42:34.034535	872962302
131	\N	view_tag	tag:عطور	2026-05-02 23:42:42.1629	872962302
132	\N	view_tag	tag:قهوة	2026-05-02 23:43:03.555647	872962302
133	\N	view_tag	tag:منزل	2026-05-02 23:43:07.087	872962302
134	\N	back	\N	2026-05-02 23:43:09.771308	872962302
135	\N	view_all	\N	2026-05-02 23:43:11.916141	872962302
136	\N	request_code	brand:🔎 البحث عن كود	2026-05-02 23:43:32.703313	872962302
137	\N	end_session	\N	2026-05-02 23:43:39.843779	872962302
138	\N	start	\N	2026-05-02 23:43:50.555862	872962302
139	\N	unknown_input	text:طيب لو كتبت لك يدوي وش تبي تقول	2026-05-02 23:44:01.850553	872962302
140	\N	unknown_input	text:غبي يعني	2026-05-02 23:44:09.039804	872962302
141	\N	idle_alert	\N	2026-05-02 23:46:48.059946	891358114
142	\N	start	\N	2026-05-02 23:51:41.450693	5226637502
143	\N	lang_pick	code:ar_sa;device:iPhone	2026-05-02 23:51:44.238522	5226637502
144	\N	search	keyword:شاهد;found:True	2026-05-02 23:51:53.334187	5226637502
145	شاهد	copy_coupon	\N	2026-05-02 23:51:55.969879	5226637502
146	شاهد	click_link	\N	2026-05-02 23:51:59.350868	5226637502
147	شاهد	reaction_heart	\N	2026-05-02 23:53:19.882548	5226637502
148	\N	idle_alert	\N	2026-05-02 23:57:50.711003	894158532
149	\N	idle_alert	\N	2026-05-02 23:59:51.408632	872962302
150	\N	idle_alert	\N	2026-05-03 00:07:53.548293	5226637502
151	\N	idle_alert	\N	2026-05-03 21:10:56.609713	872962302
152	\N	idle_alert	\N	2026-05-03 21:10:57.088863	891358114
153	\N	idle_alert	\N	2026-05-03 21:10:57.490621	650035493
154	\N	idle_alert	\N	2026-05-03 21:10:57.881775	5226637502
155	\N	idle_alert	\N	2026-05-03 21:10:58.440468	894158532
156	\N	start	\N	2026-05-03 21:40:24.133197	650035493
157	\N	view_all	\N	2026-05-03 21:40:37.936054	650035493
158	\N	end_session	\N	2026-05-03 21:40:42.340351	650035493
159	\N	start	\N	2026-05-03 21:40:45.887521	650035493
160	\N	start	\N	2026-05-03 21:45:39.189997	650035493
161	\N	end_session	\N	2026-05-03 21:46:56.627028	650035493
162	\N	start	\N	2026-05-03 21:47:06.352514	650035493
163	\N	idle_alert	\N	2026-05-03 21:54:17.65757	872962302
164	\N	idle_alert	\N	2026-05-03 21:54:18.121404	891358114
165	\N	idle_alert	\N	2026-05-03 21:54:18.453164	5226637502
166	\N	idle_alert	\N	2026-05-03 21:54:18.791384	894158532
167	\N	end_session	\N	2026-05-03 21:55:00.939321	650035493
168	\N	start	\N	2026-05-03 21:56:51.099522	650035493
169	\N	unknown_input	text:سلام	2026-05-03 22:03:09.593484	894158532
170	\N	view_sections	\N	2026-05-03 22:03:15.06369	894158532
171	\N	view_tag	tag:أطفال	2026-05-03 22:03:17.386304	894158532
172	\N	start	\N	2026-05-03 22:04:41.806577	894158532
173	\N	view_sections	\N	2026-05-03 22:05:33.634144	894158532
174	\N	view_tag	tag:أطفال	2026-05-03 22:05:36.645974	894158532
175	كلود1	copy_coupon	\N	2026-05-03 22:05:40.335792	894158532
176	كلود1	click_link	\N	2026-05-03 22:05:41.324533	894158532
177	\N	start	\N	2026-05-03 22:06:55.230859	5226637502
178	\N	idle_alert	\N	2026-05-03 22:12:21.522642	650035493
179	\N	idle_alert	\N	2026-05-03 22:21:22.679411	894158532
180	\N	idle_alert	\N	2026-05-03 22:22:38.834937	5226637502
181	\N	start	\N	2026-05-03 22:24:46.146428	650035493
182	\N	end_session	\N	2026-05-03 22:24:50.964087	650035493
183	\N	start	\N	2026-05-03 22:24:56.720048	650035493
184	\N	view_all	\N	2026-05-03 22:24:59.182681	650035493
185	\N	end_session	\N	2026-05-03 22:25:03.491293	650035493
186	\N	start	\N	2026-05-03 22:33:16.795182	650035493
187	\N	start	\N	2026-05-03 22:33:31.667087	650035493
188	\N	end_session	\N	2026-05-03 22:42:50.852418	650035493
189	\N	idle_alert	\N	2026-05-03 22:42:51.0218	872962302
190	\N	idle_alert	\N	2026-05-03 22:42:51.400711	891358114
191	\N	idle_alert	\N	2026-05-03 22:42:51.754849	5226637502
192	\N	idle_alert	\N	2026-05-03 22:42:52.324811	894158532
193	\N	start	\N	2026-05-03 22:43:14.140114	650035493
194	\N	start	\N	2026-05-03 22:45:54.73876	894158532
195	\N	view_sections	\N	2026-05-03 22:46:04.781627	894158532
196	\N	view_tag	tag:رقمي	2026-05-03 22:46:09.571081	894158532
197	شاهد	copy_coupon	\N	2026-05-03 22:46:12.324413	894158532
198	شاهد	click_link	\N	2026-05-03 22:46:15.428877	894158532
199	\N	back	\N	2026-05-03 22:46:34.047872	894158532
200	\N	request_code	brand:شاهد	2026-05-03 22:46:47.033934	894158532
201	\N	search	keyword:شاهد;found:True	2026-05-03 22:47:12.380097	894158532
202	\N	end_session	\N	2026-05-03 22:53:47.855129	650035493
203	\N	start	\N	2026-05-03 22:53:50.456869	650035493
204	\N	end_session	\N	2026-05-03 22:53:54.698192	650035493
205	\N	start	\N	2026-05-03 22:54:17.398804	650035493
206	\N	end_session	\N	2026-05-03 22:54:23.784261	650035493
207	\N	start	\N	2026-05-03 22:58:03.131361	650035493
208	\N	end_session	\N	2026-05-03 22:58:06.882211	650035493
209	\N	start	\N	2026-05-03 22:58:45.30836	650035493
210	\N	end_session	\N	2026-05-03 22:58:53.434379	650035493
211	\N	start	\N	2026-05-03 23:01:07.566916	650035493
212	\N	end_session	\N	2026-05-03 23:01:10.576286	650035493
213	\N	idle_alert	\N	2026-05-03 23:02:55.344133	894158532
214	\N	start	\N	2026-05-03 23:07:52.920164	650035493
215	\N	lang_pick	code:ar_sa;device:Android	2026-05-03 23:07:58.490805	650035493
216	\N	end_session	\N	2026-05-03 23:08:05.096323	650035493
217	\N	start	\N	2026-05-03 23:08:07.479792	650035493
218	\N	start	\N	2026-05-03 23:14:59.652556	894158532
219	\N	lang_pick	code:en_us;device:Android	2026-05-03 23:15:03.290899	894158532
220	\N	end_session	\N	2026-05-03 23:15:06.971673	894158532
221	\N	start	\N	2026-05-03 23:15:10.115409	894158532
222	\N	lang_pick	code:ar_sa;device:Android	2026-05-03 23:15:42.869748	894158532
223	\N	end_session	\N	2026-05-03 23:15:58.016035	894158532
224	\N	idle_alert	\N	2026-05-03 23:23:58.94214	650035493
225	\N	idle_alert	\N	2026-05-03 23:31:00.425024	894158532
226	\N	start	\N	2026-05-03 23:53:50.564355	650035493
227	\N	view_sections	\N	2026-05-03 23:53:55.444492	650035493
228	\N	view_tag	tag:رقمي	2026-05-03 23:54:01.09933	650035493
229	\N	view_tag	tag:ازياء	2026-05-03 23:54:06.136477	650035493
230	\N	view_tag	tag:أزياء	2026-05-03 23:54:08.685913	650035493
231	\N	view_tag	tag:أطفال	2026-05-03 23:54:11.806663	650035493
232	\N	view_tag	tag:الكترونيات	2026-05-03 23:54:14.440425	650035493
233	\N	back	\N	2026-05-03 23:54:22.679155	650035493
234	\N	view_all	\N	2026-05-03 23:54:25.578964	650035493
235	\N	end_session	\N	2026-05-03 23:54:41.551558	650035493
236	\N	idle_alert	\N	2026-05-03 23:58:22.923038	894158532
237	\N	start	\N	2026-05-03 23:59:57.996944	650035493
238	\N	view_all	\N	2026-05-04 00:00:06.106896	650035493
239	\N	view_sections	\N	2026-05-04 00:00:26.97956	650035493
240	\N	view_tag	tag:عطور	2026-05-04 00:00:32.50626	650035493
241	\N	view_sections	\N	2026-05-04 00:00:39.9138	650035493
242	\N	view_tag	tag:منزل	2026-05-04 00:00:42.69719	650035493
243	\N	view_sections	\N	2026-05-04 00:00:49.390796	650035493
244	\N	end_session	\N	2026-05-04 00:00:54.937648	650035493
245	\N	unknown_input	text:بدء الاستخدام 🚀	2026-05-04 00:01:37.714552	894158532
246	\N	start	\N	2026-05-04 00:01:37.80444	894158532
247	\N	view_sections	\N	2026-05-04 00:01:49.395997	894158532
248	\N	view_tag	tag:تجميل	2026-05-04 00:02:02.570371	894158532
249	\N	view_sections	\N	2026-05-04 00:03:05.602342	894158532
250	\N	view_tag	tag:رقمي	2026-05-04 00:03:07.789555	894158532
251	\N	view_sections	\N	2026-05-04 00:03:13.728635	894158532
252	\N	view_tag	tag:رقمي	2026-05-04 00:03:16.247187	894158532
253	\N	view_sections	\N	2026-05-04 00:03:18.451969	894158532
254	\N	view_tag	tag:منزل	2026-05-04 00:03:20.299089	894158532
255	\N	view_sections	\N	2026-05-04 00:03:28.645663	894158532
256	\N	view_tag	tag:تجميل	2026-05-04 00:03:31.003108	894158532
257	\N	view_sections	\N	2026-05-04 00:03:36.379175	894158532
258	\N	view_tag	tag:ازياء	2026-05-04 00:03:39.624855	894158532
259	\N	view_all	\N	2026-05-04 00:03:47.810961	894158532
260	\N	unknown_input	text:نون	2026-05-04 00:04:00.464645	894158532
261	\N	view_all	\N	2026-05-04 00:05:41.282684	650035493
262	\N	idle_alert	\N	2026-05-04 15:30:23.13887	650035493
263	\N	unknown_input	text:ممتاز	2026-05-04 15:30:23.139067	894158532
264	\N	start	\N	2026-05-04 15:30:23.258483	894158532
265	\N	start	\N	2026-05-04 15:30:23.262878	894158532
266	\N	idle_alert	\N	2026-05-04 15:30:23.547478	894158532
267	\N	start	\N	2026-05-04 15:30:26.349375	650035493
268	\N	unknown_input	text:الو	2026-05-04 15:30:26.354941	650035493
269	\N	start	\N	2026-05-04 15:30:26.446611	650035493
270	\N	unknown_input	text:نون	2026-05-04 15:30:37.401864	650035493
271	\N	idle_alert	\N	2026-05-04 15:45:27.969355	894158532
272	\N	unknown_input	text:.	2026-05-04 15:45:27.969723	650035493
273	\N	start	\N	2026-05-04 15:45:28.07375	650035493
274	\N	unknown_input	text:نون	2026-05-04 15:47:04.151943	650035493
275	\N	idle_alert	\N	2026-05-04 15:54:38.440351	894158532
276	\N	start	\N	2026-05-04 15:55:03.288419	650035493
277	\N	search	keyword:نون;found:True	2026-05-04 15:55:18.466053	650035493
278	\N	view_all	\N	2026-05-04 15:58:04.838455	650035493
279	\N	view_sections	\N	2026-05-04 15:58:11.776264	650035493
280	\N	search	keyword:نون;found:True	2026-05-04 16:10:43.92731	650035493
281	\N	search	keyword:نون;found:True	2026-05-04 16:10:49.274524	650035493
282	\N	search	keyword:هلا;found:False	2026-05-04 16:10:53.391951	650035493
283	\N	view_all	\N	2026-05-04 16:10:57.007988	650035493
284	\N	search	keyword:نون;found:True	2026-05-04 16:19:42.946092	650035493
285	\N	search	keyword:شاهد;found:True	2026-05-04 16:19:53.054376	650035493
286	\N	idle_alert	\N	2026-05-04 16:21:21.317931	894158532
287	\N	idle_alert	\N	2026-05-04 16:35:40.648497	650035493
288	\N	end_session	\N	2026-05-04 16:37:12.776838	650035493
289	\N	idle_alert	\N	2026-05-04 16:52:50.929006	650035493
290	\N	idle_alert	\N	2026-05-04 16:52:51.324581	894158532
291	\N	view_all	\N	2026-05-04 16:59:28.132612	650035493
292	\N	idle_alert	\N	2026-05-04 17:01:09.280412	650035493
293	\N	idle_alert	\N	2026-05-04 17:01:09.596003	894158532
\.


--
-- Data for Name: api_partners; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.api_partners (partner_id, partner_name, api_endpoint, usage_limit, status, api_key, api_secret, extra_headers) FROM stdin;
\.


--
-- Data for Name: app_monitor; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.app_monitor (log_id, log_type, action_details, created_at) FROM stdin;
\.


--
-- Data for Name: auto_rules; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auto_rules (rule_id, rule_name, is_active, settings, last_run) FROM stdin;
\.


--
-- Data for Name: available_channels; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.available_channels (channel_id, channel_name, telegram_id, is_active) FROM stdin;
\.


--
-- Data for Name: bot_dynamic_buttons; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bot_dynamic_buttons (button_id, button_text, button_callback, is_active, display_order) FROM stdin;
\.


--
-- Data for Name: bot_users; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.bot_users (telegram_id, username, joined_at, last_seen, fav_store_inferred, store_copy_count, fav_tag_inferred, tag_visit_count, user_status, visited_clicks, country, city, device_type, search_date_timestamp, manual_favorites, copied_coupons_history, interests, marketing_segment, spy_behavior_logs, spy_behavior, loyalty_rank, lang, name_en) FROM stdin;
650035493	salahasiri	2026-05-03 23:07:52.79336	2026-05-04 16:19:50.530036	1	4	أزياء	18	Active	8	المملكة العربية السعودية	الرياض	Android	\N	\N	{2,3,كلود1,نون11111}	\N	مخلص 💎	\N	\N	مميز ⭐	ar	\N
894158532	fros2220	2026-05-03 23:14:59.577033	2026-05-04 15:30:23.215674	شاهد	5	رقمي	10	Active	3	المملكة العربية السعودية	الرياض	Android	\N	\N	{شاهد,كلود1,نون50}	\N	صياد عروض 🎯	\N	\N	نشط 🟢	ar	\N
\.


--
-- Data for Name: broadcast_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.broadcast_logs (id, message_text, image_url, target_audience, sent_by, sent_at, delivery_count) FROM stdin;
\.


--
-- Data for Name: categories_tags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.categories_tags (id, tag_name, priority_score, visit_count, total_interactions, is_trending, click_count, "Tag_clicks") FROM stdin;
1	ازياء	0	0	0	عادي	0	0
2	الكترونيات	0	0	0	عادي	0	0
\.


--
-- Data for Name: channel_ads_queue; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.channel_ads_queue (ad_id, ad_title, ad_link, ad_category, ad_coupon, ad_note, scheduled_time, status, created_at, target_channel) FROM stdin;
\.


--
-- Data for Name: competitor_watch; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.competitor_watch (id, store_name, last_code, status, discount_rate) FROM stdin;
\.


--
-- Data for Name: content_studio_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.content_studio_logs (id, product_name, platform, ad_text, created_at, bg_color, text_color) FROM stdin;
\.


--
-- Data for Name: direct_search; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.direct_search (id, search_keyword, store_id, search_date, user_found, platform, name_en) FROM stdin;
1	ترند2	\N	2026-05-01 17:11:59.410366	t	TelegramBot	\N
2	نون	\N	2026-05-01 19:22:59.844292	t	TelegramBot	\N
3	ازياء	\N	2026-05-01 19:25:36.022726	t	TelegramBot	\N
4	اطفال	\N	2026-05-01 19:26:29.446612	f	TelegramBot	\N
5	نون	\N	2026-05-01 19:27:01.948846	t	TelegramBot	\N
6	شاهد	\N	2026-05-02 23:51:53.28583	t	TelegramBot	\N
7	شاهد	\N	2026-05-03 22:47:12.328398	t	TelegramBot	\N
8	نون	\N	2026-05-04 15:55:18.412538	t	TelegramBot	\N
9	نون	\N	2026-05-04 16:10:43.879852	t	TelegramBot	\N
10	نون	\N	2026-05-04 16:10:49.230902	t	TelegramBot	\N
11	هلا	\N	2026-05-04 16:10:53.34559	f	TelegramBot	\N
12	نون	\N	2026-05-04 16:19:42.897309	t	TelegramBot	\N
13	شاهد	\N	2026-05-04 16:19:53.006956	t	TelegramBot	\N
\.


--
-- Data for Name: flash_offers_queue; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.flash_offers_queue (offer_id, offer_title, reward_points, duration_minutes, target_coupon, status, created_at) FROM stdin;
\.


--
-- Data for Name: franchise_agents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.franchise_agents (agent_id, agent_name, region, profit_share, join_date) FROM stdin;
\.


--
-- Data for Name: invoice_verifications; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.invoice_verifications (invoice_id, user_handle, status) FROM stdin;
\.


--
-- Data for Name: loyalty_history; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.loyalty_history (id, user_id, action_type, points_earned, log_date) FROM stdin;
\.


--
-- Data for Name: loyalty_settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.loyalty_settings (setting_key, setting_value) FROM stdin;
\.


--
-- Data for Name: master; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.master (id, store_id, affiliate_link, public_coupon, extra_offer, store_bio, priority_score, discount_value, store_tags, my_coupon, first_time, last_time, total_link_clicks, total_coupon_copies, total_search_hits, performance_status, visit_categorie, target_category, total_clicks, is_trending, click_count, copy_clicks, link_clicks, name_en) FROM stdin;
7	5	http://localhost:8501/	4	4	444444444444444444444	عادي	4			2026-04-27	2026-05-23	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
8	نون	http://localhost:8501/	نون	نوون	نون متجر صغير	عادي	نوووون			2026-04-27	2026-05-16	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
9	نون2	2	22	2	222	عادي	2			2026-04-27	2026-04-29	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
10	999	9	9	9	9	عادي	9			2026-04-27	2026-05-30	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
11	نون11	1	1	1	نبذه	عادي	1			2026-04-28	2026-04-28	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
15	تجربة الترند	رابط	كوبون ترند	شحن ترند	وصف الترند	مهم	نسبة الترند	{أزياء,عطور,إلكترونيات,منزل,أطفال,تجميل,سفر,قهوة}		2026-04-29	2026-06-18	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
13	نون جديد	http://localhost:8502/	نون جديد	شحن	وصف متجر نون	عادي	25	{الكترونيات}		2026-04-28	2026-05-31	1	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
12	صلاح	http://localhost:8502/	صلاح1 	1	تجربة النبذه	عادي	11	{ازياء,الكترونيات}	5	2026-04-28	2026-05-02	0	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
14	نون11111	http://localhost:8502/	نون11	11	تجربه حيه للنبذه	عادي	11	{عطور,قهوة}	11	2026-04-28	2026-05-29	1	1	0	معتدل	0	\N	0	عادي	0	0	0	\N
5	3	3	3	3	تجربه جديده 4	عادي	3			2026-04-27	2026-05-30	0	1	0	معتدل	0	\N	0	عادي	0	0	0	\N
6	1	1	1	1	1	عادي	1			2026-04-27	2026-05-23	2	0	0	معتدل	0	\N	0	عادي	0	0	0	\N
17	كلود1	http://localhost:8501/	كلود1	كلود	تجربة كلود	عادي	كلود	{أزياء,عطور,إلكترونيات,منزل,أطفال,تجميل,سفر,قهوة,اكسسوارات}		2026-05-01	2026-06-12	2	2	0	معتدل	0	\N	0	عادي	0	0	0	\N
16	ترند2	ترند2	2	2	ترند عادي	عادي	2	{أزياء,عطور,إلكترونيات,منزل,أطفال,تجميل,سفر,قهوة}		2026-04-29	2026-06-26	2	0	0	معتدل	0	\N	0	ترند 🔥	0	0	0	\N
4	2	2	2	2	222	عادي	2			2026-04-27	2026-05-23	1	1	0	معتدل	0	\N	0	ترند 🔥	0	0	0	\N
19	شاهد	https://shahid.mbc.net/ar/series/%D8%A7%D9%84%D8%B3%D8%AA-%D9%85%D9%88%D9%86%D8%A7%D9%84%D9%8A%D8%B2%D8%A7-%D8%A7%D9%84%D9%85%D9%88%D8%B3%D9%85-1/season-49923660656271-49923660640266	شاهد15		متجر متخصص المنتجات الرقميه 	عادي	25%	{رقمي}		2026-05-02	2026-06-01	3	3	0	معتدل	0	\N	0	عادي	0	0	0	shahid
18	نون50	55555555555555	50	50	5050505050	عادي	50	{أزياء}		2026-05-02	2026-06-30	0	2	0	معتدل	0	\N	0	عادي	0	0	0	noon
\.


--
-- Data for Name: prediction_logs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.prediction_logs (id, search_hour, search_count, store_name, log_date) FROM stdin;
\.


--
-- Data for Name: product_comparisons; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.product_comparisons (id, store_id, product_name, price, affiliate_link, public_coupon, discount_value, extra_offer, priority_score, created_at, store_name) FROM stdin;
\.


--
-- Data for Name: search_analytics; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.search_analytics (id, search_query, search_count, last_searched, name_en) FROM stdin;
\.


--
-- Data for Name: seasonal_events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.seasonal_events (event_id, event_name, event_date, bot_status, ai_suggestion, emotional_tip) FROM stdin;
\.


--
-- Data for Name: security_blacklist; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.security_blacklist (block_id, target_value, reason, block_date) FROM stdin;
\.


--
-- Data for Name: security_settings; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.security_settings (setting_key, setting_value) FROM stdin;
\.


--
-- Data for Name: security_threats; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.security_threats (threat_id, threat_type, source_val, action_taken, detection_time) FROM stdin;
\.


--
-- Data for Name: sent_coupon_messages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.sent_coupon_messages (chat_id, message_id, store_id, user_id, sent_at, name_en) FROM stdin;
650035493	695	ترند2	\N	2026-05-02 18:48:23.833667	\N
650035493	696	2	\N	2026-05-02 18:48:24.215974	\N
650035493	697	تجربة الترند	\N	2026-05-02 18:48:24.635735	\N
650035493	698	كلود1	\N	2026-05-02 18:48:24.90226	\N
650035493	699	5	\N	2026-05-02 18:48:25.273539	\N
650035493	700	نون11111	\N	2026-05-02 18:48:25.50673	\N
650035493	701	3	\N	2026-05-02 18:48:25.741965	\N
650035493	702	1	\N	2026-05-02 18:48:25.954515	\N
650035493	703	نون جديد	\N	2026-05-02 18:48:26.190065	\N
650035493	704	نون	\N	2026-05-02 18:48:26.535	\N
650035493	710	كلود1	\N	2026-05-02 18:48:48.601615	\N
650035493	722	2	\N	2026-05-02 22:45:08.970411	\N
650035493	723	ترند2	\N	2026-05-02 22:45:09.299708	\N
650035493	724	تجربة الترند	\N	2026-05-02 22:45:09.723734	\N
650035493	725	نون جديد	\N	2026-05-02 22:45:10.047829	\N
650035493	726	نون11111	\N	2026-05-02 22:45:10.294321	\N
650035493	727	3	\N	2026-05-02 22:45:10.520898	\N
650035493	728	1	\N	2026-05-02 22:45:10.77415	\N
650035493	729	كلود1	\N	2026-05-02 22:45:10.99543	\N
650035493	730	5	\N	2026-05-02 22:45:11.316799	\N
650035493	731	نون50	\N	2026-05-02 22:45:11.573132	\N
650035493	737	2	\N	2026-05-02 22:47:54.324319	\N
650035493	738	ترند2	\N	2026-05-02 22:47:54.827519	\N
650035493	739	تجربة الترند	\N	2026-05-02 22:47:55.233863	\N
650035493	740	نون جديد	\N	2026-05-02 22:47:55.560542	\N
650035493	741	نون11111	\N	2026-05-02 22:47:55.842837	\N
650035493	742	3	\N	2026-05-02 22:47:56.164611	\N
650035493	743	1	\N	2026-05-02 22:47:56.68495	\N
650035493	744	كلود1	\N	2026-05-02 22:47:57.022345	\N
650035493	745	5	\N	2026-05-02 22:47:57.371065	\N
650035493	746	نون50	\N	2026-05-02 22:47:57.700598	\N
894158532	767	2	894158532	2026-05-02 23:33:04.367101	\N
894158532	768	ترند2	894158532	2026-05-02 23:33:04.678874	\N
894158532	769	تجربة الترند	894158532	2026-05-02 23:33:04.910702	\N
894158532	770	نون جديد	894158532	2026-05-02 23:33:05.174261	\N
894158532	771	نون11111	894158532	2026-05-02 23:33:05.416665	\N
894158532	772	3	894158532	2026-05-02 23:33:05.794068	\N
894158532	773	1	894158532	2026-05-02 23:33:06.011355	\N
894158532	774	كلود1	894158532	2026-05-02 23:33:06.400189	\N
894158532	775	5	894158532	2026-05-02 23:33:06.665246	\N
894158532	776	نون50	894158532	2026-05-02 23:33:07.021403	\N
894158532	787	شاهد	894158532	2026-05-02 23:40:54.363551	\N
872962302	797	ترند2	872962302	2026-05-02 23:42:02.635107	\N
872962302	798	تجربة الترند	872962302	2026-05-02 23:42:02.880607	\N
872962302	799	كلود1	872962302	2026-05-02 23:42:03.254766	\N
872962302	802	كلود1	872962302	2026-05-02 23:42:12.923275	\N
872962302	809	ترند2	872962302	2026-05-02 23:42:19.631742	\N
872962302	810	تجربة الترند	872962302	2026-05-02 23:42:19.904527	\N
872962302	811	كلود1	872962302	2026-05-02 23:42:20.156821	\N
872962302	812	نون50	872962302	2026-05-02 23:42:20.425978	\N
872962302	815	نون جديد	872962302	2026-05-02 23:42:25.03948	\N
872962302	818	شاهد	872962302	2026-05-02 23:42:28.60531	\N
872962302	821	ترند2	872962302	2026-05-02 23:42:34.572708	\N
872962302	822	تجربة الترند	872962302	2026-05-02 23:42:34.820671	\N
872962302	823	كلود1	872962302	2026-05-02 23:42:35.061129	\N
872962302	826	ترند2	872962302	2026-05-02 23:42:42.686429	\N
872962302	827	تجربة الترند	872962302	2026-05-02 23:42:42.926724	\N
872962302	828	نون11111	872962302	2026-05-02 23:42:43.189373	\N
872962302	829	كلود1	872962302	2026-05-02 23:42:43.527822	\N
872962302	832	ترند2	872962302	2026-05-02 23:43:04.345803	\N
872962302	833	تجربة الترند	872962302	2026-05-02 23:43:04.5952	\N
872962302	834	نون11111	872962302	2026-05-02 23:43:04.958645	\N
872962302	835	كلود1	872962302	2026-05-02 23:43:05.207971	\N
872962302	838	ترند2	872962302	2026-05-02 23:43:07.741478	\N
872962302	839	تجربة الترند	872962302	2026-05-02 23:43:08.000764	\N
872962302	840	كلود1	872962302	2026-05-02 23:43:08.227861	\N
872962302	844	ترند2	872962302	2026-05-02 23:43:12.297773	\N
872962302	845	2	872962302	2026-05-02 23:43:12.73868	\N
872962302	846	تجربة الترند	872962302	2026-05-02 23:43:12.96603	\N
872962302	847	نون جديد	872962302	2026-05-02 23:43:13.358365	\N
872962302	848	نون11111	872962302	2026-05-02 23:43:13.577398	\N
872962302	849	3	872962302	2026-05-02 23:43:13.785738	\N
872962302	850	1	872962302	2026-05-02 23:43:14.037667	\N
872962302	851	كلود1	872962302	2026-05-02 23:43:14.373594	\N
872962302	852	نون50	872962302	2026-05-02 23:43:14.583868	\N
872962302	853	5	872962302	2026-05-02 23:43:14.850485	\N
5226637502	873	شاهد	5226637502	2026-05-02 23:51:53.588716	\N
650035493	888	2	650035493	2026-05-03 21:40:38.406099	\N
650035493	889	ترند2	650035493	2026-05-03 21:40:38.65149	\N
650035493	890	تجربة الترند	650035493	2026-05-03 21:40:38.889551	\N
650035493	891	نون جديد	650035493	2026-05-03 21:40:39.176763	\N
650035493	892	نون11111	650035493	2026-05-03 21:40:39.401234	\N
650035493	893	شاهد	650035493	2026-05-03 21:40:39.615072	\N
650035493	894	3	650035493	2026-05-03 21:40:39.851441	\N
650035493	895	1	650035493	2026-05-03 21:40:40.084233	\N
650035493	896	كلود1	650035493	2026-05-03 21:40:40.31841	\N
650035493	897	5	650035493	2026-05-03 21:40:40.57828	\N
894158532	922	ترند2	894158532	2026-05-03 22:03:18.062051	\N
894158532	923	تجربة الترند	894158532	2026-05-03 22:03:18.301892	\N
894158532	924	كلود1	894158532	2026-05-03 22:03:18.52488	\N
894158532	931	ترند2	894158532	2026-05-03 22:05:37.289495	\N
894158532	932	تجربة الترند	894158532	2026-05-03 22:05:37.685375	\N
894158532	933	كلود1	894158532	2026-05-03 22:05:37.942969	\N
650035493	947	ترند2	650035493	2026-05-03 22:24:59.59762	\N
650035493	948	2	650035493	2026-05-03 22:24:59.937443	\N
650035493	949	تجربة الترند	650035493	2026-05-03 22:25:00.16712	\N
650035493	950	نون جديد	650035493	2026-05-03 22:25:00.382156	\N
650035493	951	نون11111	650035493	2026-05-03 22:25:00.596163	\N
650035493	952	شاهد	650035493	2026-05-03 22:25:00.809708	\N
650035493	953	3	650035493	2026-05-03 22:25:01.142037	\N
650035493	954	1	650035493	2026-05-03 22:25:01.472741	\N
650035493	955	كلود1	650035493	2026-05-03 22:25:01.701791	\N
650035493	956	5	650035493	2026-05-03 22:25:01.930495	\N
894158532	977	شاهد	894158532	2026-05-03 22:46:10.43884	\N
894158532	989	شاهد	894158532	2026-05-03 22:47:12.734064	\N
650035493	1041	ترند2	650035493	2026-05-03 23:54:09.293311	\N
650035493	1042	تجربة الترند	650035493	2026-05-03 23:54:09.527207	\N
650035493	1043	كلود1	650035493	2026-05-03 23:54:09.786765	\N
650035493	1044	نون50	650035493	2026-05-03 23:54:10.124872	\N
650035493	1047	ترند2	650035493	2026-05-03 23:54:12.486082	\N
650035493	1048	تجربة الترند	650035493	2026-05-03 23:54:12.786824	\N
650035493	1049	كلود1	650035493	2026-05-03 23:54:13.071419	\N
650035493	1052	نون جديد	650035493	2026-05-03 23:54:15.053615	\N
650035493	1054	شاهد	650035493	2026-05-03 23:54:17.574234	\N
650035493	1058	2	650035493	2026-05-03 23:54:25.892825	\N
650035493	1059	ترند2	650035493	2026-05-03 23:54:26.136269	\N
650035493	1060	تجربة الترند	650035493	2026-05-03 23:54:26.359505	\N
650035493	1061	نون جديد	650035493	2026-05-03 23:54:26.611578	\N
650035493	1062	نون11111	650035493	2026-05-03 23:54:26.918795	\N
650035493	1063	3	650035493	2026-05-03 23:54:27.162727	\N
650035493	1064	1	650035493	2026-05-03 23:54:27.43468	\N
650035493	1065	كلود1	650035493	2026-05-03 23:54:27.698605	\N
650035493	1066	شاهد	650035493	2026-05-03 23:54:27.955579	\N
650035493	1067	5	650035493	2026-05-03 23:54:28.223925	\N
894158532	1076	1	894158532	2026-05-04 00:02:02.843015	\N
650035493	1073	2	650035493	2026-05-04 00:00:06.222474	\N
650035493	1096	نون	650035493	2026-05-04 15:58:04.982939	\N
650035493	1101	شاهد	650035493	2026-05-04 15:55:18.512189	\N
650035493	1110	نون11111	650035493	2026-05-04 16:59:28.390478	\N
\.


--
-- Data for Name: support_tickets; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.support_tickets (id, username, telegram_id, message, status, created_at) FROM stdin;
\.


--
-- Data for Name: traffic_sources; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.traffic_sources (id, source_name, visit_count) FROM stdin;
\.


--
-- Data for Name: unavailable_codes_requests; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.unavailable_codes_requests (id, user_id, brand_name, requested_at, user_email, master_id, name_en) FROM stdin;
1	650035493	➕ طلب كود	2026-05-01 17:12:21.646998	\N	\N	\N
2	650035493	نون	2026-05-01 17:12:31.450481	\N	\N	\N
3	650035493	نون	2026-05-01 19:21:52.418042	\N	\N	\N
4	650035493	نون	2026-05-01 19:22:14.885214	\N	\N	\N
5	650035493	فراس	2026-05-01 19:26:20.517885	\N	\N	\N
6	891358114	🛑 إنهاء	2026-05-02 23:30:50.828869	\N	\N	\N
7	894158532	🏷️ أزياء	2026-05-02 23:32:59.33525	\N	\N	\N
8	872962302	🔎 البحث عن كود	2026-05-02 23:43:32.663112	\N	\N	\N
9	894158532	شاهد	2026-05-03 22:46:46.989608	\N	\N	\N
\.


--
-- Data for Name: user_preferences; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_preferences (user_id, preferred_categories, location_city, last_targeted_broadcast, opt_in_notifications) FROM stdin;
\.


--
-- Data for Name: users_master; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.users_master (user_id, username, points, rank, main_interest, loyalty_score, total_savings, last_active, birth_date, favorite_brands, meta_data, name_en) FROM stdin;
\.


--
-- Name: action_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.action_logs_id_seq', 293, true);


--
-- Name: api_partners_partner_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.api_partners_partner_id_seq', 1, false);


--
-- Name: app_monitor_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.app_monitor_log_id_seq', 1, false);


--
-- Name: auto_rules_rule_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auto_rules_rule_id_seq', 1, false);


--
-- Name: available_channels_channel_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.available_channels_channel_id_seq', 1, false);


--
-- Name: bot_dynamic_buttons_button_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.bot_dynamic_buttons_button_id_seq', 1, false);


--
-- Name: broadcast_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.broadcast_logs_id_seq', 1, false);


--
-- Name: categories_tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.categories_tags_id_seq', 16, true);


--
-- Name: channel_ads_queue_ad_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.channel_ads_queue_ad_id_seq', 1, false);


--
-- Name: competitor_watch_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.competitor_watch_id_seq', 1, false);


--
-- Name: content_studio_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.content_studio_logs_id_seq', 1, false);


--
-- Name: direct_search_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.direct_search_id_seq', 13, true);


--
-- Name: flash_offers_queue_offer_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.flash_offers_queue_offer_id_seq', 1, false);


--
-- Name: franchise_agents_agent_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.franchise_agents_agent_id_seq', 1, false);


--
-- Name: invoice_verifications_invoice_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.invoice_verifications_invoice_id_seq', 1, false);


--
-- Name: loyalty_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.loyalty_history_id_seq', 1, false);


--
-- Name: master_input_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.master_input_id_seq', 19, true);


--
-- Name: prediction_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.prediction_logs_id_seq', 1, false);


--
-- Name: product_comparisons_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.product_comparisons_id_seq', 1, false);


--
-- Name: search_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.search_analytics_id_seq', 1, false);


--
-- Name: seasonal_events_event_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.seasonal_events_event_id_seq', 1, false);


--
-- Name: security_blacklist_block_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.security_blacklist_block_id_seq', 1, false);


--
-- Name: security_threats_threat_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.security_threats_threat_id_seq', 1, false);


--
-- Name: support_tickets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.support_tickets_id_seq', 1, false);


--
-- Name: traffic_sources_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.traffic_sources_id_seq', 1, false);


--
-- Name: unavailable_codes_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.unavailable_codes_requests_id_seq', 9, true);


--
-- Name: action_logs action_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.action_logs
    ADD CONSTRAINT action_logs_pkey PRIMARY KEY (id);


--
-- Name: api_partners api_partners_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_partners
    ADD CONSTRAINT api_partners_pkey PRIMARY KEY (partner_id);


--
-- Name: app_monitor app_monitor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_monitor
    ADD CONSTRAINT app_monitor_pkey PRIMARY KEY (log_id);


--
-- Name: auto_rules auto_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auto_rules
    ADD CONSTRAINT auto_rules_pkey PRIMARY KEY (rule_id);


--
-- Name: auto_rules auto_rules_rule_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auto_rules
    ADD CONSTRAINT auto_rules_rule_name_key UNIQUE (rule_name);


--
-- Name: available_channels available_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.available_channels
    ADD CONSTRAINT available_channels_pkey PRIMARY KEY (channel_id);


--
-- Name: bot_dynamic_buttons bot_dynamic_buttons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_dynamic_buttons
    ADD CONSTRAINT bot_dynamic_buttons_pkey PRIMARY KEY (button_id);


--
-- Name: bot_users bot_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bot_users
    ADD CONSTRAINT bot_users_pkey PRIMARY KEY (telegram_id);


--
-- Name: broadcast_logs broadcast_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broadcast_logs
    ADD CONSTRAINT broadcast_logs_pkey PRIMARY KEY (id);


--
-- Name: categories_tags categories_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories_tags
    ADD CONSTRAINT categories_tags_pkey PRIMARY KEY (id);


--
-- Name: categories_tags categories_tags_tag_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories_tags
    ADD CONSTRAINT categories_tags_tag_name_key UNIQUE (tag_name);


--
-- Name: channel_ads_queue channel_ads_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.channel_ads_queue
    ADD CONSTRAINT channel_ads_queue_pkey PRIMARY KEY (ad_id);


--
-- Name: competitor_watch competitor_watch_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.competitor_watch
    ADD CONSTRAINT competitor_watch_pkey PRIMARY KEY (id);


--
-- Name: competitor_watch competitor_watch_store_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.competitor_watch
    ADD CONSTRAINT competitor_watch_store_name_key UNIQUE (store_name);


--
-- Name: content_studio_logs content_studio_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.content_studio_logs
    ADD CONSTRAINT content_studio_logs_pkey PRIMARY KEY (id);


--
-- Name: direct_search direct_search_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.direct_search
    ADD CONSTRAINT direct_search_pkey PRIMARY KEY (id);


--
-- Name: flash_offers_queue flash_offers_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.flash_offers_queue
    ADD CONSTRAINT flash_offers_queue_pkey PRIMARY KEY (offer_id);


--
-- Name: franchise_agents franchise_agents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.franchise_agents
    ADD CONSTRAINT franchise_agents_pkey PRIMARY KEY (agent_id);


--
-- Name: invoice_verifications invoice_verifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_verifications
    ADD CONSTRAINT invoice_verifications_pkey PRIMARY KEY (invoice_id);


--
-- Name: loyalty_history loyalty_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loyalty_history
    ADD CONSTRAINT loyalty_history_pkey PRIMARY KEY (id);


--
-- Name: loyalty_settings loyalty_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.loyalty_settings
    ADD CONSTRAINT loyalty_settings_pkey PRIMARY KEY (setting_key);


--
-- Name: master master_input_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.master
    ADD CONSTRAINT master_input_pkey PRIMARY KEY (id);


--
-- Name: prediction_logs prediction_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prediction_logs
    ADD CONSTRAINT prediction_logs_pkey PRIMARY KEY (id);


--
-- Name: product_comparisons product_comparisons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_comparisons
    ADD CONSTRAINT product_comparisons_pkey PRIMARY KEY (id);


--
-- Name: search_analytics search_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_analytics
    ADD CONSTRAINT search_analytics_pkey PRIMARY KEY (id);


--
-- Name: seasonal_events seasonal_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seasonal_events
    ADD CONSTRAINT seasonal_events_pkey PRIMARY KEY (event_id);


--
-- Name: security_blacklist security_blacklist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_blacklist
    ADD CONSTRAINT security_blacklist_pkey PRIMARY KEY (block_id);


--
-- Name: security_blacklist security_blacklist_target_value_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_blacklist
    ADD CONSTRAINT security_blacklist_target_value_key UNIQUE (target_value);


--
-- Name: security_settings security_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_settings
    ADD CONSTRAINT security_settings_pkey PRIMARY KEY (setting_key);


--
-- Name: security_threats security_threats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_threats
    ADD CONSTRAINT security_threats_pkey PRIMARY KEY (threat_id);


--
-- Name: sent_coupon_messages sent_coupon_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sent_coupon_messages
    ADD CONSTRAINT sent_coupon_messages_pkey PRIMARY KEY (chat_id, message_id);


--
-- Name: support_tickets support_tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.support_tickets
    ADD CONSTRAINT support_tickets_pkey PRIMARY KEY (id);


--
-- Name: traffic_sources traffic_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.traffic_sources
    ADD CONSTRAINT traffic_sources_pkey PRIMARY KEY (id);


--
-- Name: traffic_sources traffic_sources_source_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.traffic_sources
    ADD CONSTRAINT traffic_sources_source_name_key UNIQUE (source_name);


--
-- Name: unavailable_codes_requests unavailable_codes_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unavailable_codes_requests
    ADD CONSTRAINT unavailable_codes_requests_pkey PRIMARY KEY (id);


--
-- Name: user_preferences user_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_preferences
    ADD CONSTRAINT user_preferences_pkey PRIMARY KEY (user_id);


--
-- Name: users_master users_master_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users_master
    ADD CONSTRAINT users_master_pkey PRIMARY KEY (user_id);


--
-- Name: idx_action_logs_action_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_action_logs_action_type ON public.action_logs USING btree (action_type);


--
-- Name: idx_action_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_action_logs_user_id ON public.action_logs USING btree (user_id);


--
-- Name: idx_action_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_action_time ON public.action_logs USING btree (action_time);


--
-- Name: idx_logs_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_logs_time ON public.action_logs USING btree (action_time);


--
-- Name: idx_logs_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_logs_type ON public.action_logs USING btree (action_type);


--
-- Name: idx_master_name_en_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_master_name_en_trgm ON public.master USING gin (name_en public.gin_trgm_ops);


--
-- Name: idx_master_tags_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_master_tags_trgm ON public.master USING gin (store_tags public.gin_trgm_ops);


--
-- Name: idx_store_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_store_action ON public.action_logs USING btree (store_id);


--
-- PostgreSQL database dump complete
--

\unrestrict DDIoN2yKfb7Jy5JlgvL6towggaMQRXgEEAi68br3dMcteVErxdT6tvDJRzREBs0

