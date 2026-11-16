import { useShell, useTabDeclaration } from './shell.js'

const NOTHING = { globe: {}, timeline: null }

// Home: the welcome, then every other tool, listed from the registry.
export default function StartTab() {
  const { catalog, tabs, openTab } = useShell()
  useTabDeclaration(NOTHING)
  return (
    <article className="welcome" aria-labelledby="welcome-heading">
      <p className="eyebrow">NASA Earth science · Trend detective</p>
      <h2 id="welcome-heading">The same planet changes differently from place to place.</h2>
      <p className="welcome-lede">
        The engine compares {catalog.regions.length} Regions across {catalog.variables.length}{' '}
        Variables measured by NASA missions and models, and looks for places changing in ways
        that contrast. Pick how you want to start.
      </p>
      <div className="experiences">
        {tabs.filter((tab) => tab.id !== 'start').map((tab, index) => (
          <button
            key={tab.id}
            className={index === 0 ? 'experience' : 'experience experience-quiet'}
            onClick={() => openTab(tab.id)}
          >
            <span className="experience-title">{tab.label}</span>
            <span className="experience-text">{tab.description}</span>
          </button>
        ))}
      </div>
    </article>
  )
}
