import { promises as fs } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { writeFiles } from './starter';

describe('writeFiles', () => {
  let root: string;
  beforeEach(async () => {
    root = await fs.mkdtemp(path.join(os.tmpdir(), 'starter-'));
  });
  afterEach(() => fs.rm(root, { recursive: true, force: true }));

  it('writes nested files into the workspace', async () => {
    const written = await writeFiles(root, { 'src/main.ts': 'x', Dockerfile: 'FROM node' });
    expect(written).toEqual(['Dockerfile', 'src/main.ts']);
    expect(await fs.readFile(path.join(root, 'src', 'main.ts'), 'utf8')).toBe('x');
  });

  it('refuses paths outside the workspace', async () => {
    await expect(writeFiles(root, { '../evil': 'x' })).rejects.toThrow('outside the workspace');
    await expect(writeFiles(root, { [path.resolve('/etc/passwd')]: 'x' })).rejects.toThrow('outside the workspace');
  });
});
