import React, {useState} from 'react';
import ReactDOM from 'react-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import Savegame from './Savegame';
import Viewer from './Viewer';

function Main() {
  const [data, setData] = useState(null)

  return (
    <div>
      <div className="card border-info bg-warning container mt-1 text-center">
        <p>Savegames have to be made with <a target="_new" href="https://github.com/OpenTTD/OpenTTD/pull/9322">PR9322</a></p>
        <p>Don't have a valid savegame?<br /><a href="ottdc_pzsg5.sav">Download the converted #openttdcoop ProZone Server Game #5 here</a>.</p>
      </div>

      <Savegame setData={setData} />
      <Viewer data={data} />
    </div>
  )
}

ReactDOM.render(
  <React.StrictMode>
    <Main />
  </React.StrictMode>,
  document.getElementById('root')
);
