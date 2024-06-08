import("pathfinder.road", "RoadPathFinder", 4);

class NoOpAIImportingPathfinder extends AIController 
{
  function Start();
}

function NoOpAIImportingPathfinder::Start()
{
  // Set the company name
  local i = 1
  local name = "NoOpAIImportingPathfinder"
  while (!AICompany.SetName(name)) {
    name = "NoOpAIImportingPathfinder #" + ++i
  }

  while (true)
  {
    AILog.Info("Start of NoOpAIImportingPathfinder " + this.GetTick());
    this.Sleep(50);
  }
}
