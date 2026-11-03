-- air-dj 테이블. Supabase 대시보드 > SQL Editor에서 한 번 실행한다 (다시 실행해도 안전).
-- 쓰기는 파이 receiver가 secret 키(service_role)로만 한다.

create table if not exists public.gesture_commands (
    id          bigint generated always as identity primary key,
    received_at timestamptz not null,           -- 파이가 제스처를 받은 시각
    command     text not null,                  -- play | pause | next | prev | volume_up | volume_down
    label       text not null,                  -- 명령을 만든 제스처 라벨
    created_at  timestamptz not null default now()
);

create table if not exists public.gesture_frames (
    id          bigint generated always as identity primary key,
    received_at timestamptz not null,
    label       text not null,                  -- no_hand는 저장하지 않는다
    score       real not null
);

create index if not exists gesture_commands_received_at_idx on public.gesture_commands (received_at desc);
create index if not exists gesture_frames_received_at_idx on public.gesture_frames (received_at desc);

-- SQL로 만든 테이블은 RLS가 자동으로 켜지지 않는다. 정책은 두지 않는다 = publishable 키로는 접근 불가.
alter table public.gesture_commands enable row level security;
alter table public.gesture_frames enable row level security;

-- secret 키는 RLS를 우회하지만 테이블 grant는 따로 필요하다.
grant select, insert on table public.gesture_commands to service_role;
grant select, insert on table public.gesture_frames to service_role;
