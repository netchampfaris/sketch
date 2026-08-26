# Design the Fixture API and the stubbed resources

Type: grilling
Status: open
Blocked by: 

## Question

How does an agent declare Fixtures, and how do createResource, createListResource, and createDocumentResource resolve against them in the Runtime? Decide: fixture file name and shape, how a resource key maps to a fixture, what insert/update/delete do (mutate in-memory only), and what an unknown resource returns. The answer must be simple enough to fit in the served skill.
