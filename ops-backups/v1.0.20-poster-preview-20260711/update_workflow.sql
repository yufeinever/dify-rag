begin;

create table mmb_backup_v1020_poster_async_workflows as
select *
from workflows
where app_id = '13f7a06c-769d-474c-8863-613e9aeb25cb';

with patched as (
  select w.id,
         jsonb_set(
           w.graph::jsonb,
           '{nodes}',
           (
             select jsonb_agg(
               case
                 when node->>'id' = 'job_status_parse_001' then
                   jsonb_set(
                     node,
                     '{data,code}',
                     to_jsonb(
                       replace(
                         node->'data'->>'code',
                         $old$        markdown += f"![生成海报]({url})\n\n[打开原图]({url})"
        if thumb != url:
            markdown += f"\n\n[缩略图]({thumb})"$old$,
                         $new$        markdown += f"![生成海报预览]({thumb})\n\n[查看/下载高清原图]({url})"$new$
                       )
                     )
                   )
                 else node
               end
               order by ord
             )
             from jsonb_array_elements(w.graph::jsonb->'nodes') with ordinality as n(node, ord)
           )
         )::text as graph
  from workflows w
  where w.app_id = '13f7a06c-769d-474c-8863-613e9aeb25cb'
)
update workflows w
set graph = patched.graph,
    updated_at = now()
from patched
where w.id = patched.id;

commit;

select version,
       graph like '%![生成海报]({url})%' as uses_full_image,
       graph like '%![生成海报预览]({thumb})%' as uses_thumbnail
from workflows
where app_id = '13f7a06c-769d-474c-8863-613e9aeb25cb'
order by version;
