-- NORA ingestion integrity
-- Applied to the connected Supabase project.
update public.nora_regions
set geometry = jsonb_build_object('type','bbox','coordinates',jsonb_build_array(-55.2,-15.2,-51.3,-10.5)),
    grid_size_deg = 0.1
where region_id = 'alto_xingu' and geometry is null;

create unique index if not exists nora_observations_natural_key
on public.nora_observations(region_id, variable_id, cell_id, observed_at);

create index if not exists nora_observations_region_date_idx
on public.nora_observations(region_id, observed_at);

create index if not exists nora_observations_variable_date_idx
on public.nora_observations(variable_id, observed_at);

insert into public.nora_variables
(key,name,domain,unit,spatial_resolution,temporal_resolution,source_id,description)
select 'evi','EVI','vegetation','index','250 m','16-day',5,
       'Enhanced Vegetation Index from MODIS MOD13Q1 V6.1'
where not exists (select 1 from public.nora_variables where key='evi');
