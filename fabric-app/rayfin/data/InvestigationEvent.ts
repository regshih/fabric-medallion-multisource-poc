import { entity, role, uuid, text, date } from '@microsoft/rayfin-core';

// Append-only and owner-scoped. Assignment is deliberately not an auth claim.
// No anonymous, update, or delete permission is generated.
@entity()
@role('authenticated', ['create', 'read'], {
  policy: (claims, item) => claims.sub.eq(item.user_id),
})
export class InvestigationEvent {
  @uuid() id!: string;
  @uuid() caseId!: string;
  @text({ min: 11, max: 11, regex: /^CUST-[0-9]{6}$/ }) CustomerID!: string;
  @text({ min: 1, max: 255 }) user_id!: string;
  @text({ min: 4, max: 7, regex: /^(created|updated|note)$/ }) eventType!: string;
  @text({ min: 4, max: 13, regex: /^(Open|Investigating|Escalated|Resolved)$/ }) status!: string;
  @text({ min: 1, max: 120 }) assignee!: string;
  @text({ max: 2000 }) note!: string;
  @date() createdAt!: Date;
}
