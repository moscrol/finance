import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import type { ResearchEvolutionView } from '../types';
import { ResearchEvolutionPanel } from './ResearchEvolutionPanel';

function view(status: string): ResearchEvolutionView {
  const ref = {kind: 'judgment', id: 'j1', namespace: 'judgments', version_or_hash: 'h1', ref: 'judgments.jsonl:j1', scope: {}};
  const ok = {status: 'ok', reason: null, synthetic: false};
  return {
    schema_version: 'research-evolution-view/v1', owner_user_id: 'default', conversation_id: 'conv1',
    view_version: 'v1', view_digest: 'd1', generated_at: '2026-09-14T08:00:00Z',
    maintenance: {id: 'm1', as_of: '2026-09-14', knowledge_cutoff: '2026-09-14', pit_grade: 'strict', hindsight: false,
      gaps: [], counts: {}, items: [{id: 'item1', item_version: 'v1', object_ref: ref, before: [], current: [],
        change_type: 'content_changed', reason_code: 'hash_changed', epistemic_state: 'requires_review',
        condition_result: null, condition_role: null, as_of: '2026-09-14', knowledge_cutoff: '2026-09-14', pit_grade: 'strict',
        gaps: [], action: 'review_evidence', status: 'rejudgment_requested', management_revision: 1,
        management: {rejudgment: {request_event_id: 'evt1'}}}],
      run_links: [{item_id: 'item1', run_id: 'run1', conversation_id: 'conv1', request_event_id: 'evt1', run_status: status}]},
    priority: null, diagnostics: null, receipt_refs: {validation: [], product_value: []},
    module_status: {maintenance: ok, priority: ok, diagnostics: ok, validation_receipts: ok, product_value_receipts: ok}, gaps: [],
    inputs: {as_of: '2026-09-14', knowledge_cutoff: '2026-09-14', budget_minutes: null, bindings: 1,
      trackable_objects: [{object_ref: {...ref, id: 'j2', ref: 'judgments.jsonl:j2'}, kind: 'judgment', title: '本轮新成果', recorded_at: '2026-09-14', bound: false, binding_id: null, gaps: [], candidate_refs: []}]},
  };
}

it('W4: an open confirmation form becomes submittable after its only run completes', () => {
  const onAction = vi.fn();
  const {rerender} = render(<ResearchEvolutionPanel view={view('running')} onAction={onAction} />);
  fireEvent.click(screen.getByRole('button', {name: '确认成果'}));
  expect(screen.getByText(/还没有已完成的核查 run/)).toBeInTheDocument();
  // App refreshes the projection on the run-terminal event; the form stays mounted.
  rerender(<ResearchEvolutionPanel view={view('completed')} onAction={onAction} />);
  const form = screen.getByLabelText('确认成果');
  const runSelect = within(form).getByLabelText('本轮核查 run');
  expect(runSelect).toHaveValue('run1');
  fireEvent.change(within(form).getByLabelText('成果判断'), {target: {value: 'judgments.jsonl:j2'}});
  const confirm = within(form).getByRole('button', {name: '确认这条判断是本轮成果'});
  expect(confirm).toBeEnabled();
  fireEvent.click(confirm);
  expect(onAction).toHaveBeenCalledWith(expect.objectContaining({run_id: 'run1', new_judgment_ref: 'judgments.jsonl:j2'}));
});
