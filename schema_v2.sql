-- ============================================================================
--  SCHEMA V2: công ty -> nhóm thiết bị -> thiết bị, và nội dung -> PLAYLIST -> lịch
--
--      organization (công ty)
--        ├─ device_group (nhóm: Cửa hàng Bắc / Nam)
--        │     └─ device (TV)
--        ├─ media        (video / ảnh / youtube)           <- kho nội dung
--        └─ playlist     (danh sách phát)
--              └─ playlist_item (nội dung nào, thứ tự, hiện bao lâu)
--
--      schedule = "NHÓM nào phát PLAYLIST nào, vào giờ / ngày nào"
--
--  Chạy MỘT LẦN trong Supabase > SQL Editor (chạy trọn file, nó nằm trong 1 giao dịch:
--  lỗi ở đâu thì toàn bộ tự hoàn tác, dữ liệu cũ không bị hỏng).
--
--  Giả định bảng hiện tại của bạn (theo sơ đồ):
--    organization(org_id, name)
--    device_group(group_id, org_id, name)
--    device(device_id, name, status bool, ip, last_heartbeat, group_id, app_version,
--           current_schedule_id, current_video_id, created_at, online bool)
--    video(id, title, url, org_id, created_at)
--    schedule(schedule_id, start_time, end_time, video_id, start_date, end_date,
--             group_id, is_active, priority)
-- ============================================================================
begin;

-- ---------------------------------------------------------------- 1. device
alter table device alter column status set default false;          -- TV mới = chưa duyệt
alter table device alter column online drop not null;              -- cột này không còn dùng (xem cuối file)
alter table device alter column online set default false;

alter table device rename column current_video_id to current_media_id;
alter table device add column if not exists playback_state text;   -- 'loading' | 'playing' | 'error' | 'idle'

-- ---------------------------------------------------------------- 2. video -> media
alter table video rename to media;
alter table media rename column id to media_id;

update media set org_id = (select min(org_id) from organization) where org_id is null;
alter table media alter column org_id set not null;

alter table media add column if not exists media_type   text   not null default 'video';
alter table media add column if not exists duration_sec int;     -- ảnh / youtube BẮT BUỘC (hiện bao lâu); video thì tùy chọn
alter table media add column if not exists size_bytes   bigint;
alter table media add constraint media_type_ok
    check (media_type in ('video', 'image', 'youtube'));
alter table media add constraint media_duration_ok
    check (media_type = 'video' or coalesce(duration_sec, 0) > 0);
alter table media alter column url set not null;

-- ---------------------------------------------------------------- 3. playlist
create table playlist (
    playlist_id bigint generated always as identity primary key,
    org_id      bigint not null references organization(org_id),
    name        text   not null,
    created_at  timestamptz not null default now()
);

create table playlist_item (
    item_id      bigint generated always as identity primary key,
    playlist_id  bigint not null references playlist(playlist_id) on delete cascade,
    media_id     bigint not null references media(media_id),
    position     int    not null,                 -- thứ tự phát: 1, 2, 3...
    duration_sec int,                              -- ghi đè thời gian hiện (null = dùng của media)
    unique (playlist_id, position)
);
create index on playlist_item (media_id);

-- ---------------------------------------------------------------- 4. schedule: video_id -> playlist_id
alter table schedule add column playlist_id bigint references playlist(playlist_id);

-- mỗi (công ty của nhóm, video cũ) -> 1 playlist 1 phần tử, lịch cũ trỏ vào playlist đó
alter table playlist add column legacy_media_id bigint;       -- tạm, chỉ để ghép dữ liệu cũ

insert into playlist (org_id, name, legacy_media_id)
select distinct g.org_id, 'Playlist: ' || m.title, m.media_id
from schedule s
join device_group g on g.group_id = s.group_id
join media m        on m.media_id = s.video_id;

insert into playlist_item (playlist_id, media_id, position)
select playlist_id, legacy_media_id, 1 from playlist where legacy_media_id is not null;

update schedule s
set playlist_id = p.playlist_id
from device_group g, playlist p
where g.group_id = s.group_id
  and p.org_id = g.org_id
  and p.legacy_media_id = s.video_id;

alter table playlist drop column legacy_media_id;
alter table schedule drop column video_id;
create index on schedule (group_id);
-- (schedule.playlist_id được phép null chỉ với dòng lịch mồ côi cũ, các dòng đó bị bỏ qua khi phát)

-- ---------------------------------------------------------------- 5. ràng buộc "cùng công ty"
--  playlist chỉ chứa media của CÙNG công ty; nhóm chỉ phát playlist của CÙNG công ty.
create or replace function check_item_org() returns trigger language plpgsql as $$
begin
    if (select org_id from media where media_id = new.media_id)
       is distinct from (select org_id from playlist where playlist_id = new.playlist_id) then
        raise exception 'media % khác công ty với playlist %', new.media_id, new.playlist_id;
    end if;
    return new;
end $$;
create trigger trg_item_org before insert or update on playlist_item
    for each row execute function check_item_org();

create or replace function check_schedule_org() returns trigger language plpgsql as $$
begin
    if new.playlist_id is not null and new.group_id is not null and
       (select org_id from playlist where playlist_id = new.playlist_id)
       is distinct from (select org_id from device_group where group_id = new.group_id) then
        raise exception 'playlist % khác công ty với nhóm %', new.playlist_id, new.group_id;
    end if;
    return new;
end $$;
create trigger trg_schedule_org before insert or update on schedule
    for each row execute function check_schedule_org();

-- ---------------------------------------------------------------- 6. view: TV nào đang online
--  Online = heartbeat trong 3 phút gần nhất (3 lần chu kỳ 60 giây). KHÔNG lưu cột "online"
--  vì TV chết đột ngột sẽ không kịp ghi "offline".
create or replace view device_status as
select d.device_id, d.name, d.status as approved,
       g.name as group_name, o.name as org_name,
       d.last_heartbeat,
       (d.last_heartbeat is not null and d.last_heartbeat > now() - interval '3 minutes') as is_online,
       d.playback_state, d.current_media_id, d.current_schedule_id, d.ip, d.app_version
from device d
left join device_group g on g.group_id = d.group_id
left join organization o on o.org_id   = g.org_id;

-- ---------------------------------------------------------------- 7. hàm (RPC) cho TV gọi
--  TV chỉ gọi 4 hàm này, KHÔNG đọc thẳng các bảng -> bật/tắt RLS của bảng không ảnh hưởng TV.
drop function if exists device_heartbeat(text, text, bigint, bigint, text, text);
drop function if exists get_device_status(text);
drop function if exists register_device(text);
drop function if exists get_device_schedule(text);
drop function if exists get_video_url(bigint);

-- 7.1 TV báo "còn sống" + đang phát gì. Giờ do SERVER ghi.
create function device_heartbeat(
    p_device_id text, p_ip text default null, p_media_id bigint default null,
    p_schedule_id bigint default null, p_playback_state text default null,
    p_app_version text default null
) returns void language sql security definer set search_path = public as $$
    update device set
        last_heartbeat      = now(),
        ip                  = coalesce(p_ip, ip),
        app_version         = coalesce(p_app_version, app_version),
        current_media_id    = p_media_id,
        current_schedule_id = p_schedule_id,
        playback_state      = p_playback_state
    where device_id = p_device_id;
$$;

-- 7.2 trạng thái duyệt: 'approved' | 'pending' | null (TV chưa có trong bảng)
create function get_device_status(p_device_id text) returns text
language sql stable security definer set search_path = public as $$
    select case when status then 'approved' else 'pending' end
    from device where device_id = p_device_id;
$$;

-- 7.3 TV mới tự xin phép: tạo dòng chưa duyệt (có rồi thì không làm gì)
create function register_device(p_device_id text) returns text
language sql security definer set search_path = public as $$
    insert into device (device_id) values (p_device_id) on conflict (device_id) do nothing;
    select case when status then 'approved' else 'pending' end from device where device_id = p_device_id;
$$;

-- 7.4 TOÀN BỘ lịch của nhóm mà TV thuộc về, kèm danh sách nội dung của từng playlist, trong 1 lần gọi.
--  Thứ tự: lịch ngày đặc biệt trước, rồi priority cao trước, rồi ngày bắt đầu mới trước, rồi giờ sớm trước.
--  App chọn dòng ĐẦU TIÊN khớp ngày/giờ hiện tại.
create function get_device_schedules(p_device_id text) returns jsonb
language sql stable security definer set search_path = public as $$
    select coalesce(jsonb_agg(to_jsonb(q) order by
               (q.start_date is null), q.priority desc nulls last, q.start_date desc nulls last, q.start_time), '[]'::jsonb)
    from (
        select s.schedule_id, s.playlist_id, s.start_time, s.end_time, s.start_date, s.end_date, s.priority,
               (select coalesce(jsonb_agg(jsonb_build_object(
                           'item_id',      i.item_id,
                           'position',     i.position,
                           'media_id',     m.media_id,
                           'media_type',   m.media_type,
                           'title',        m.title,
                           'url',          m.url,
                           'size_bytes',   m.size_bytes,
                           'duration_sec', coalesce(i.duration_sec, m.duration_sec)
                       ) order by i.position), '[]'::jsonb)
                from playlist_item i join media m on m.media_id = i.media_id
                where i.playlist_id = s.playlist_id) as items
        from schedule s
        join device d on d.group_id = s.group_id
        where d.device_id = p_device_id and s.is_active and s.playlist_id is not null
    ) q;
$$;

commit;

-- ============================================================================
--  VÍ DỤ ĐẦY ĐỦ (bỏ comment, sửa cho đúng rồi chạy): công ty có Bắc + Nam, mỗi nhóm một playlist
-- ============================================================================
-- insert into organization (name) values ('Công ty ABC');
--
-- insert into device_group (org_id, name)
--   select org_id, 'Cửa hàng Bắc' from organization where name = 'Công ty ABC';
-- insert into device_group (org_id, name)
--   select org_id, 'Cửa hàng Nam' from organization where name = 'Công ty ABC';
--
-- -- kho nội dung (3 loại)
-- insert into media (org_id, title, media_type, url, duration_sec)
--   select org_id, 'Video giới thiệu', 'video',   'https://res.cloudinary.com/xxx/video/upload/intro.mp4', null
--   from organization where name = 'Công ty ABC';
-- insert into media (org_id, title, media_type, url, duration_sec)
--   select org_id, 'Banner khuyến mãi', 'image',  'https://res.cloudinary.com/xxx/image/upload/sale.jpg', 8
--   from organization where name = 'Công ty ABC';
-- insert into media (org_id, title, media_type, url, duration_sec)
--   select org_id, 'TVC trên YouTube', 'youtube', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 30
--   from organization where name = 'Công ty ABC';
--
-- -- playlist "Bắc": video -> ảnh 8 giây -> youtube 30 giây (thứ tự theo position)
-- insert into playlist (org_id, name)
--   select org_id, 'Playlist Bắc' from organization where name = 'Công ty ABC';
-- insert into playlist_item (playlist_id, media_id, position)
--   select (select playlist_id from playlist where name = 'Playlist Bắc'), media_id,
--          case media_type when 'video' then 1 when 'image' then 2 else 3 end
--   from media where title in ('Video giới thiệu', 'Banner khuyến mãi', 'TVC trên YouTube');
--
-- -- gán playlist cho NHÓM, phát cả ngày (mọi TV trong nhóm Bắc phát theo; sửa 1 chỗ là cả nhóm đổi)
-- insert into schedule (group_id, playlist_id, start_time, end_time)
--   values ((select group_id from device_group where name = 'Cửa hàng Bắc'),
--           (select playlist_id from playlist where name = 'Playlist Bắc'), '00:00', '23:59:59');
--
-- -- duyệt TV mới (đọc mã trên màn hình TV) và xếp vào nhóm
-- update device set status = true, name = 'TV sảnh',
--        group_id = (select group_id from device_group where name = 'Cửa hàng Bắc')
--   where device_id = 'K7QM-4TXA';
--
-- -- xem TV nào đang online, đang phát gì
-- select * from device_status order by org_name, group_name, device_id;

-- ============================================================================
--  DỌN DẸP (vài ngày sau, khi chắc chắn mọi thứ ổn):
-- ============================================================================
-- alter table device drop column online;      -- đã có view device_status.is_online thay thế
