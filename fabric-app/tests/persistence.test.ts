import { expect, it } from 'vitest';
import { DemoRepository } from '../src/repository';
import { buildDemo, DEMO_IDENTITY } from '../src/demo';
import { makeEvent } from '../src/domain';

it('persists acknowledged events across repository instances and rejects duplicate writes', async () => {
  const first = new DemoRepository();
  const event = makeEvent(DEMO_IDENTITY, buildDemo().profiles[0]);
  await first.append(event);
  expect(await new DemoRepository().events()).toContainEqual(event);
  await expect(first.append(event)).rejects.toThrow('Could not save');
});
it('rejects a forged demo event owner before writing', async () => {
  const event = makeEvent(
    { id: 'other-person', email: 'other@example.test' },
    buildDemo().profiles[0],
  );
  await expect(new DemoRepository().append(event)).rejects.toThrow('does not belong');
});
