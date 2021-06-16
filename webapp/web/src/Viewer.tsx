import React from 'react'
import JSONTree from 'react-json-tree'

function Viewer(props: any) {
  return (
    <div className={`card border-info container mt-2`}>
      <JSONTree data={props.data} />
    </div>
  )
}

export default Viewer;
