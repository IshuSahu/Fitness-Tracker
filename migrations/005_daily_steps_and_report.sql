-- Manual daily entries from a smartwatch, and the report change that follows.
--
-- Sleep duration and step count come off a watch that already measures both
-- accurately, so they are typed in rather than computed. sleep_hours stops
-- being derived from the bed/wake times (those stay on screen for reference
-- only); steps is new.

alter table daily_logs add column if not exists steps integer;

-- weekly_report, unchanged except for average steps.
create or replace function weekly_report(p_start date, p_end date, p_user_id uuid)
returns text
language plpgsql
security definer
as $$
declare
  v_block_name text; v_week_no int; v_report text := '';
  v_ex record; v_flags text := '';
  v_prev_start date := p_start - (p_end - p_start + 1);
  v_prev_end   date := p_start - 1;
  v_start_w numeric; v_end_w numeric; v_avg_w numeric; v_last4 text;
  v_days_target int; v_avg_kcal numeric; v_avg_sleep numeric; v_low_sleep int;
  v_avg_steps int; v_days int := (p_end - p_start + 1);
begin
  select b.name, ts.week_no into v_block_name, v_week_no
  from training_session ts join block b on b.id = ts.block_id
  where ts.date between p_start and p_end order by ts.date limit 1;

  v_report := format(E'# Weekly Report — Block "%s", Week %s (%s–%s)\n## Training\n',
    coalesce(v_block_name,'Unnamed'), coalesce(v_week_no::text,'—'),
    to_char(p_start,'DD Mon'), to_char(p_end,'DD Mon'));

  for v_ex in
    select e.name as ex_name, sl.exercise_id,
           array_agg(sl.load_kg || '×' || sl.reps order by sl.set_index) as sets_arr,
           max(sl.e1rm_kg) as cur_e1rm, sum(sl.tonnage_kg) as tonnage
    from set_log sl
    join training_session ts on ts.id = sl.session_id
    join exercise e on e.id = sl.exercise_id
    where ts.date between p_start and p_end and sl.warmup = false
    group by e.name, sl.exercise_id order by e.name
  loop
    declare v_prev_e1rm numeric; v_delta numeric; v_miss int;
    begin
      select max(sl2.e1rm_kg) into v_prev_e1rm
      from set_log sl2 join training_session ts2 on ts2.id = sl2.session_id
      where ts2.date between v_prev_start and v_prev_end
        and sl2.exercise_id = v_ex.exercise_id and sl2.warmup = false;
      v_delta := case when v_prev_e1rm is not null then round(v_ex.cur_e1rm - v_prev_e1rm,1) end;

      v_report := v_report || format('- %s — sets: [%s] · e1rm %skg (%s) · tonnage %skg'||E'\n',
        v_ex.ex_name, array_to_string(v_ex.sets_arr, ', '), round(v_ex.cur_e1rm,1),
        case when v_delta is null then 'no prior data'
             when v_delta >= 0 then '+'||v_delta||' vs last wk' else v_delta||' vs last wk' end,
        round(v_ex.tonnage,0));

      select consecutive_misses into v_miss from lift_state where exercise_id = v_ex.exercise_id;
      if v_miss >= 2 then v_flags := v_flags || v_ex.ex_name || ' (miss x'||v_miss||'); '; end if;
    end;
  end loop;

  v_report := v_report || 'Flags: ' || case when v_flags = '' then 'none' else rtrim(v_flags,'; ') end || E'\n\n';

  select round(avg(weight_kg),1) into v_avg_w from weight_logs where user_id = p_user_id and log_date between p_start and p_end;
  select weight_kg into v_start_w from weight_logs where user_id = p_user_id and log_date between p_start and p_end order by log_date asc limit 1;
  select weight_kg into v_end_w  from weight_logs where user_id = p_user_id and log_date between p_start and p_end order by log_date desc limit 1;

  select string_agg(round(w,1)::text, ', ' order by wk) into v_last4
  from (select date_trunc('week', log_date) as wk, avg(weight_kg) as w
        from weight_logs where user_id = p_user_id and log_date between (p_end - 27) and p_end
        group by wk order by wk) t;

  v_report := v_report || '## Body' || E'\n' ||
    format('Weight: start %s → end %s (avg %s), last 4 weeks: [%s]'||E'\n\n',
      coalesce(v_start_w::text,'—'), coalesce(v_end_w::text,'—'), coalesce(v_avg_w::text,'—'), coalesce(v_last4,'—'));

  select count(*) filter (where protein_g >= 137), round(avg(kcal_eaten)),
         round(avg(sleep_hours),1), count(*) filter (where sleep_hours < 6),
         round(avg(steps))
  into v_days_target, v_avg_kcal, v_avg_sleep, v_low_sleep, v_avg_steps
  from daily_logs where user_id = p_user_id and log_date between p_start and p_end;

  v_report := v_report || '## Nutrition / Water / Sleep / Steps adherence' || E'\n' ||
    format('Days on protein target: %s/%s · avg kcal: %s · avg sleep: %sh, nights <6h: %s · avg steps: %s',
      coalesce(v_days_target,0), v_days, coalesce(v_avg_kcal::text,'—'),
      coalesce(v_avg_sleep::text,'—'), coalesce(v_low_sleep,0), coalesce(v_avg_steps::text,'—'));

  return v_report;
end;
$$;
