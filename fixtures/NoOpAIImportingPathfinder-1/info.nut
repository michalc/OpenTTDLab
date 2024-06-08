class NoOpAIImportingPathfinder extends AIInfo {
  function GetAuthor()      { return "Michal Charemza"; }
  function GetName()        { return "NoOpAIImportingPathfinder"; }
  function GetDescription() { return "A no-op AI that imports a library for testing purposes"; }
  function GetVersion()     { return 1; }
  function GetDate()        { return "2024-02-11"; }
  function CreateInstance() { return "NoOpAIImportingPathfinder"; }
  function GetShortName()   { return "NOPF"; }
  function GetAPIVersion()  { return "12"; }
}
RegisterAI(NoOpAIImportingPathfinder());
