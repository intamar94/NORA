-- NO EJECUTAR AUTOMATICAMENTE.
-- Preparado porque el proyecto Supabase tiene tablas NORA sin RLS.
-- Antes de habilitarlo hay que decidir si la interfaz será pública de solo lectura
-- o autenticada. Habilitar RLS sin políticas bloqueará el acceso.

-- Opción recomendada para una interfaz pública: lectura anónima,
-- escritura solo desde backend con service role.

alter table public.nora_regions enable row level security;
alter table public.nora_sources enable row level security;
alter table public.nora_variables enable row level security;
alter table public.nora_observations enable row level security;
alter table public.nora_analyses enable row level security;
alter table public.nora_hypotheses enable row level security;
alter table public.nora_dataset_registry enable row level security;
alter table public.nora_discovery_results enable row level security;
alter table public.nora_zone_jobs enable row level security;
alter table public.nora_source_capabilities enable row level security;
alter table public.nora_goal_runs enable row level security;
alter table public.nora_quality_checks enable row level security;
alter table public.nora_map_layers enable row level security;

-- Después de decidir el modelo de acceso, crear explícitamente las políticas.
-- Ejemplo SOLO para catálogos públicos de lectura:
-- create policy "public read nora regions" on public.nora_regions for select to anon, authenticated using (true);
-- create policy "public read nora sources" on public.nora_sources for select to anon, authenticated using (true);
-- create policy "public read nora variables" on public.nora_variables for select to anon, authenticated using (true);
-- create policy "public read nora capabilities" on public.nora_source_capabilities for select to anon, authenticated using (true);

-- NO crear políticas públicas de INSERT/UPDATE/DELETE para observaciones,
-- análisis, trabajos, controles de calidad o hipótesis. Esas escrituras deben
-- permanecer en el backend seguro.
