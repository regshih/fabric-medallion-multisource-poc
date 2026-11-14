import { createRoot } from 'react-dom/client';
import App from './App';
import { createRepository } from './repository';
import './styles.css';

const root = createRoot(document.getElementById('root')!);
root.render(<div className="startup">Preparing Signal…</div>);
createRepository()
  .then((repository) => root.render(<App repository={repository} />))
  .catch((error) =>
    root.render(
      <main className="fatal-error">
        <h1>Connection configuration required</h1>
        <p>{error instanceof Error ? error.message : 'Could not initialize the app.'}</p>
        <p>Live mode has stopped. No synthetic data has been substituted.</p>
      </main>,
    ),
  );
