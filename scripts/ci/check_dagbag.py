"""Ejecutar dentro de la imagen Airflow, sin credenciales ni datos montados."""
from airflow.dag_processing.dagbag import DagBag
bag = DagBag(dag_folder='/opt/airflow/dags')
assert not bag.import_errors, bag.import_errors
assert len(bag.dags) == 4, bag.dags.keys()
for dag in bag.dags.values():
    assert dag.max_active_runs == 1
    assert dag.timetable.__class__.__name__ == 'NullTimetable'
    assert all(task.pool == 'retailops_serial' for task in dag.tasks)
print('DagBag: cuatro DAGs reales, cero errores, cero tareas ejecutadas')
