import { useEffect, useRef } from 'react'

export default function MissingDataDialog({ inputs, onDismiss }) {
  const dialog = useRef(null)
  useEffect(() => {
    const element = dialog.current
    element.showModal()
    return () => element.close()
  }, [])
  return (
    <dialog ref={dialog} className="correlation-popup" role="alertdialog" aria-labelledby="missing-title" onCancel={event => { event.preventDefault(); onDismiss() }}>
      <h4 id="missing-title">Not enough data</h4>
      {inputs.map((item, i) => <p key={i}>{item.label ?? item.variable}: {item.message}</p>)}
      <button autoFocus type="button" onClick={onDismiss}>Dismiss missing-data message</button>
    </dialog>
  )
}
