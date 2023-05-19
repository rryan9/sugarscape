#! /usr/bin/python

import agent
import cell
import disease
import environment
import gui

import getopt
import json
import math
import random
import sys

class Sugarscape:
    def __init__(self, configuration):
        self.__configuration = configuration
        self.__timestep = 0
        self.__nextAgentID = 0
        self.__nextDiseaseID = 0
        self.__lastLoggedTimestep = 0
        environmentConfiguration = {"globalMaxSugar": configuration["environmentMaxSugar"], "sugarRegrowRate": configuration["environmentSugarRegrowRate"],
                                    "seasonInterval": configuration["environmentSeasonInterval"], "seasonalGrowbackDelay": configuration["environmentSeasonalGrowbackDelay"],
                                    "spiceConsumptionPollutionFactor": configuration["environmentSpiceConsumptionPollutionFactor"],
                                    "sugarConsumptionPollutionFactor": configuration["environmentSugarConsumptionPollutionFactor"],
                                    "spiceProductionPollutionFactor": configuration["environmentSpiceProductionPollutionFactor"],
                                    "sugarProductionPollutionFactor": configuration["environmentSugarProductionPollutionFactor"],
                                    "pollutionDiffusionDelay": configuration["environmentPollutionDiffusionDelay"], "maxCombatLoot": configuration["environmentMaxCombatLoot"],
                                    "globalMaxSpice": configuration["environmentMaxSpice"], "spiceRegrowRate": configuration["environmentSpiceRegrowRate"], "sugarscapeSeed": configuration["seed"]}
        self.__seed = configuration["seed"]
        self.__environment = environment.Environment(configuration["environmentHeight"], configuration["environmentWidth"], self, environmentConfiguration)
        self.__environmentHeight = configuration["environmentHeight"]
        self.__environmentWidth = configuration["environmentWidth"]
        self.configureEnvironment(configuration["environmentMaxSugar"], configuration["environmentMaxSpice"])
        self.__agents = []
        self.__diseases = []
        self.configureAgents(configuration["startingAgents"])
        self.configureDiseases(configuration["startingDiseases"])
        self.__gui = gui.GUI(self) if configuration["headlessMode"] == False else None
        self.__run = False # Simulation start flag
        self.__end = False # Simulation end flag
        self.__runtimeStats = {"timestep": 0, "agents": 0, "meanMetabolism": 0, "meanVision": 0, "meanWealth": 0, "meanAge": 0, "giniCoefficient": 0,
                               "meanTradePrice": 0, "meanTradeVolume": 0, "totalTradeVolume": 0, "totalWealth": 0, "maxWealth": 0, "minWealth": 0}
        self.__log = open(configuration["logfile"], 'a') if configuration["logfile"] != None else None
        self.__logAgent = None

    def addAgent(self, agent):
        self.__agents.append(agent)

    def addDisease(self, oldDisease, agent):
        diseaseID = oldDisease.getID()
        diseaseConfig = oldDisease.getConfiguration()
        newDisease = disease.Disease(diseaseID, diseaseConfig)
        agent.catchDisease(newDisease)

    def addSpicePeak(self, startX, startY, radius, maxSpice):
        height = self.__environment.getHeight()
        width = self.__environment.getWidth()
        radialDispersion = math.sqrt(max(startX, width - startX)**2 + max(startY, height - startY)**2) * (radius / width)
        seasons = True if self.__configuration["environmentSeasonInterval"] > 0 else False
        for i in range(height):
            for j in range(width):
                if self.__environment.getCell(i, j) == None:
                    newCell = cell.Cell(i, j, self.__environment)
                    if seasons == True:
                        if j >= self.__environment.getEquator():
                            newCell.setSeason("summer")
                        else:
                            newCell.setSeason("winter")
                    self.__environment.setCell(newCell, i, j)
                euclideanDistanceToStart = math.sqrt((startX - i)**2 + (startY - j)**2)
                currDispersion = 1 + maxSpice * (1 - euclideanDistanceToStart / radialDispersion)
                cellMaxCapacity = min(currDispersion, maxSpice)
                cellMaxCapacity = math.ceil(cellMaxCapacity)
                if cellMaxCapacity > self.__environment.getCell(i, j).getMaxSpice():
                    self.__environment.getCell(i, j).setMaxSpice(cellMaxCapacity)
                    self.__environment.getCell(i, j).setCurrSpice(cellMaxCapacity)

    def addSugarPeak(self, startX, startY, radius, maxSugar):
        height = self.__environment.getHeight()
        width = self.__environment.getWidth()
        radialDispersion = math.sqrt(max(startX, width - startX)**2 + max(startY, height - startY)**2) * (radius / width)
        seasons = True if self.__configuration["environmentSeasonInterval"] > 0 else False
        for i in range(height):
            for j in range(width):
                if self.__environment.getCell(i, j) == None:
                    newCell = cell.Cell(i, j, self.__environment)
                    if seasons == True:
                        if j >= self.__environment.getEquator():
                            newCell.setSeason("summer")
                        else:
                            newCell.setSeason("winter")
                    self.__environment.setCell(newCell, i, j)
                euclideanDistanceToStart = math.sqrt((startX - i)**2 + (startY - j)**2)
                currDispersion = 1 + maxSugar * (1 - euclideanDistanceToStart / radialDispersion)
                cellMaxCapacity = min(currDispersion, maxSugar)
                cellMaxCapacity = math.ceil(cellMaxCapacity)
                if cellMaxCapacity > self.__environment.getCell(i, j).getMaxSugar():
                    self.__environment.getCell(i, j).setMaxSugar(cellMaxCapacity)
                    self.__environment.getCell(i, j).setCurrSugar(cellMaxCapacity)
 
    def configureAgents(self, numAgents):
        if self.__environment == None:
            return

        activeCells = self.findActiveQuadrants()
        if len(activeCells) == 0:
            return

        totalCells = len(activeCells)
        if len(self.__agents) + numAgents > totalCells:
            print("Could not allocate {0} agents. Allocating maximum of {1}.".format(numAgents, totalCells))
            numAgents = totalCells

        # Ensure agent endowments are randomized across initial agent count to make replacements follow same distributions
        agentEndowments = self.randomizeAgentEndowments(numAgents)
        randCoords = activeCells
        random.shuffle(randCoords)

        for i in range(numAgents):
            randCoord = randCoords.pop()
            randCellX = randCoord[0]
            randCellY = randCoord[1]
            c = self.__environment.getCell(randCellX, randCellY)
            agentConfiguration = agentEndowments[i]
            agentID = self.generateAgentID()
            a = agent.Agent(agentID, self.__timestep, c, agentConfiguration)
            c.setAgent(a)
            self.__agents.append(a)

    def configureDiseases(self, numDiseases):
        numAgents = len(self.__agents)
        if numAgents == 0:
            return
        elif numAgents < numDiseases:
            numDiseases = numAgents

        diseaseEndowments = self.randomizeDiseaseEndowments(numDiseases)
        random.shuffle(self.__agents)
        diseases = []
        for i in range(numDiseases):
            diseaseID = self.generateDiseaseID()
            diseaseConfiguration = diseaseEndowments[i]
            newDisease = disease.Disease(diseaseID, diseaseConfiguration)
            diseases.append(newDisease)

        unplacedDisease = 0
        for agent in self.__agents:
            for newDisease in diseases:
                hammingDistance = agent.findNearestHammingDistanceInDisease(newDisease)["distance"]
                if hammingDistance != 0:
                    agent.catchDisease(newDisease)
                    self.__diseases.append(newDisease)
                    diseases.remove(newDisease)
                    break
        if len(diseases) > 0:
            print("Could not place {0} diseases.".format(len(diseases)))

    def configureEnvironment(self, maxSugar, maxSpice):
        height = self.__environment.getHeight()
        width = self.__environment.getWidth()
        startX1 = math.ceil(height * 0.7)
        startX2 = math.ceil(height * 0.3)
        startY1 = math.ceil(width * 0.3)
        startY2 = math.ceil(width * 0.7)
        sugarRadiusScale = 2
        radius = math.ceil(math.sqrt(sugarRadiusScale * (height + width)))
        self.addSugarPeak(startX1, startY1, radius, maxSugar)
        self.addSugarPeak(startX2, startY2, radius, maxSugar)
        
        startX1 = math.ceil(height * 0.7)
        startX2 = math.ceil(height * 0.3)
        startY1 = math.ceil(width * 0.7)
        startY2 = math.ceil(width * 0.3)
        spiceRadiusScale = 2
        radius = math.ceil(math.sqrt(spiceRadiusScale * (height + width)))
        self.addSpicePeak(startX1, startY1, radius, maxSpice)
        self.addSpicePeak(startX2, startY2, radius, maxSpice)
        self.__environment.setCellNeighbors()

    def doTimestep(self):
        self.removeDeadAgents()
        self.replaceDeadAgents()
        self.updateRuntimeStats()
        self.writeToLog()
        print("Timestep: {0}\nLiving Agents: {1}".format(self.__timestep, len(self.__agents)))
        self.__timestep += 1
        if self.__end == True or len(self.__agents) == 0:
            self.setEnd()
        else:
            self.__environment.doTimestep(self.__timestep)
            random.shuffle(self.__agents)
            for agent in self.__agents:
                agent.doTimestep(self.__timestep)
            if self.__gui != None:
                self.__gui.doTimestep()
        self.updateRuntimeStats()

    def endLog(self):
        if self.__log == None:
            return
        logString = '\t' + json.dumps(self.__runtimeStats) + "\n]"
        self.__log.write(logString)
        self.__log.flush()
        self.__log.close()

    def endSimulation(self):
        deadAgents = []
        for agent in self.__agents:
            if agent.isAlive() == False:
                deadAgents.append(agent)
        for agent in deadAgents:
            self.__agents.remove(agent)
        self.endLog()
        print(str(self))
        exit(0)

    def findActiveQuadrants(self):
        quadrants = self.__configuration["agentStartingQuadrants"]
        cellRange = []
        halfWidth = math.floor(self.__environmentWidth / 2)
        halfHeight = math.floor(self.__environmentHeight / 2)
        # Quadrant I at origin in top left corner, other quadrants in clockwise order
        if 1 in quadrants:
            quadRange = [[(i, j) for j in range(halfHeight)] for i in range(halfWidth)]
            for i in range(halfWidth):
                for j in range(halfHeight):
                    cellRange.append([i, j])
        if 2 in quadrants:
            quadRange = [[(i, j) for j in range(halfHeight)] for i in range(halfWidth, self.__environmentWidth)]
            for i in range(halfWidth, self.__environmentWidth):
                for j in range(halfHeight):
                    cellRange.append([i, j])
        if 3 in quadrants:
            quadRange = [[(i, j) for j in range(halfHeight, self.__environmentHeight)] for i in range(halfWidth, self.__environmentWidth)]
            for i in range(halfWidth, self.__environmentWidth):
                for j in range(halfHeight, self.__environmentHeight):
                    cellRange.append([i, j])
        if 4 in quadrants:
            quadRange = [[(i, j) for j in range(halfHeight, self.__environmentHeight)] for i in range(halfWidth)]
            for i in range(halfWidth):
                for j in range(halfHeight, self.__environmentHeight):
                    cellRange.append([i, j])
        return cellRange

    def generateAgentID(self):
        agentID = self.__nextAgentID
        self.__nextAgentID += 1
        return agentID

    def getAgents(self):
        return self.__agents

    def getConfiguration(self):
        return self.__configuration

    def generateDiseaseID(self):
        diseaseID = self.__nextDiseaseID
        self.__nextDiseaseID += 1
        return diseaseID

    def getEnd(self):
        return self.__end

    def getEnvironment(self):
        return self.__environment
 
    def getEnvironmentHeight(self):
        return self.__environmentHeight

    def getEnvironmentWidth(self):
        return self.__environmentWidth

    def getGUI(self):
        return self.__gui

    def getRun(self):
        return self.__run

    def getRuntimeStats(self):
        return self.__runtimeStats

    def getSeed(self):
        return self.__seed

    def getTimestep(self):
        return self.__timestep

    def pauseSimulation(self):
        while self.__run == False:
            if self.__gui != None and self.__end == False:
                self.__gui.getWindow().update()
            if self.__end == True:
                self.endSimulation()

    def printCell(self, cellX, cellY):
        cell = self.__environment.getCell(cellX, cellY)
        cellStats = "Cell ({0},{1}): {2}/{3} sugar, {4}/{5} spice, {6} pollution".format(cellX, cellY, cell.getCurrSugar(), cell.getMaxSugar(), cell.getCurrSpice(), cell.getMaxSpice(), cell.getCurrPollution())
        agent = cell.getAgent()
        if agent != None:
            agentStats = "Agent {0}: {1} timesteps old, {2} vision, {3} movement, {4} sugar, {5} spice, {6} mean metabolism".format(str(agent), agent.getAge(), agent.getVision(), agent.getMovement(), agent.getSugar(),
                                                                                                                                    agent.getSpice(), (agent.getSugarMetabolism() + agent.getSpiceMetabolism()) / 2)
            cellStats += "\n  {0}".format(agentStats)
        print(cellStats)

    def randomizeDiseaseEndowments(self, numDiseases):
        configs = self.__configuration
        sugarMetabolismPenalty = configs["diseaseSugarMetabolismPenalty"]
        spiceMetabolismPenalty = configs["diseaseSpiceMetabolismPenalty"]
        movementPenalty = configs["diseaseMovementPenalty"]
        visionPenalty = configs["diseaseVisionPenalty"]
        fertilityPenalty = configs["diseaseFertilityPenalty"]
        aggressionPenalty = configs["diseaseAggressionPenalty"]
        tagLengths = configs["diseaseTagStringLength"]

        minSugarMetabolismPenalty = sugarMetabolismPenalty[0]
        minSpiceMetabolismPenalty = spiceMetabolismPenalty[0]
        minMovementPenalty = movementPenalty[0]
        minVisionPenalty = visionPenalty[0]
        minFertilityPenalty = fertilityPenalty[0]
        minAggressionPenalty = aggressionPenalty[0]
        minTagLength = tagLengths[0]

        maxSugarMetabolismPenalty = sugarMetabolismPenalty[1]
        maxSpiceMetabolismPenalty = spiceMetabolismPenalty[1]
        maxMovementPenalty = movementPenalty[1]
        maxVisionPenalty = visionPenalty[1]
        maxFertilityPenalty = fertilityPenalty[1]
        maxAggressionPenalty = aggressionPenalty[1]
        maxTagLength = tagLengths[1]

        endowments = []
        sugarMetabolismPenalties = []
        spiceMetabolismPenalties = []
        movementPenalties = []
        visionPenalties = []
        fertilityPenalties = []
        aggressionPenalties = []
        diseaseTags = []

        currSugarMetabolismPenalty = minSugarMetabolismPenalty
        currSpiceMetabolismPenalty = minSpiceMetabolismPenalty
        currMovementPenalty = minMovementPenalty
        currVisionPenalty = minVisionPenalty
        currFertilityPenalty = minFertilityPenalty
        currAggressionPenalty = minAggressionPenalty
        currTagLength = minTagLength

        for i in range(numDiseases):
            sugarMetabolismPenalties.append(currSugarMetabolismPenalty)
            spiceMetabolismPenalties.append(currSpiceMetabolismPenalty)
            movementPenalties.append(currMovementPenalty)
            visionPenalties.append(currVisionPenalty)
            fertilityPenalties.append(currFertilityPenalty)
            aggressionPenalties.append(currAggressionPenalty)
            diseaseTags.append([random.randrange(2) for i in range(currTagLength)])

            currSugarMetabolismPenalty += 1
            currSpiceMetabolismPenalty += 1
            currMovementPenalty += 1
            currVisionPenalty += 1
            currFertilityPenalty += 1
            currAggressionPenalty += 1
            currTagLength += 1

            if currSugarMetabolismPenalty > maxSugarMetabolismPenalty:
                currSugarMetabolismPenalty = minSugarMetabolismPenalty
            if currSpiceMetabolismPenalty > maxSpiceMetabolismPenalty:
                currSpiceMetabolismPenalty = minSpiceMetabolismPenalty
            if currMovementPenalty > maxMovementPenalty:
                currMovementPenalty = minMovementPenalty
            if currVisionPenalty > maxVisionPenalty:
                currVisionPenalty = minVisionPenalty
            if currFertilityPenalty > maxFertilityPenalty:
                currFertilityPenalty = minFertilityPenalty
            if currAggressionPenalty > maxAggressionPenalty:
                currAggressionPenalty = minAggressionPenalty
            if currTagLength > maxTagLength:
                currTagLength = minTagLength

        random.shuffle(sugarMetabolismPenalties)
        random.shuffle(spiceMetabolismPenalties)
        random.shuffle(movementPenalties)
        random.shuffle(visionPenalties)
        random.shuffle(fertilityPenalties)
        random.shuffle(aggressionPenalties)
        random.shuffle(diseaseTags)

        for i in range(numDiseases):
            diseaseEndowment = {"sugarMetabolismPenalty": sugarMetabolismPenalties.pop(), "spiceMetabolismPenalty": spiceMetabolismPenalties.pop(),
                                "movementPenalty": movementPenalties.pop(), "visionPenalty": visionPenalties.pop(), "fertilityPenalty": fertilityPenalties.pop(),
                                "aggressionPenalty": aggressionPenalties.pop(), "tags": diseaseTags.pop()}
            endowments.append(diseaseEndowment)
        return endowments

    def randomizeAgentEndowments(self, numAgents):
        configs = self.__configuration
        spiceMetabolism = configs["agentSpiceMetabolism"]
        sugarMetabolism = configs["agentSugarMetabolism"]
        movement = configs["agentMovement"]
        vision = configs["agentVision"]
        startingSugar = configs["agentStartingSugar"]
        startingSpice = configs["agentStartingSpice"]
        maxAge = configs["agentMaxAge"]
        maleToFemaleRatio = configs["agentMaleToFemaleRatio"]
        femaleFertilityAge = configs["agentFemaleFertilityAge"]
        maleFertilityAge = configs["agentMaleFertilityAge"]
        femaleInfertilityAge = configs["agentFemaleInfertilityAge"]
        maleInfertilityAge = configs["agentMaleInfertilityAge"]
        tagStringLength = configs["agentTagStringLength"]
        immuneSystemLength = configs["agentImmuneSystemLength"]
        aggressionFactor = configs["agentAggressionFactor"]
        tradeFactor = configs["agentTradeFactor"]
        lookaheadFactor = configs["agentLookaheadFactor"]
        lendingFactor = configs["agentLendingFactor"]
        fertilityFactor = configs["agentFertilityFactor"]
        loanDuration = configs["agentLoanDuration"]
        baseInterestRate = configs["agentBaseInterestRate"]
        maxFriends = configs["agentMaxFriends"]
        inheritancePolicy = configs["agentInheritancePolicy"]
        ethicalFactor = configs["agentEthicalFactor"]

        configurations = {"aggressionFactor": {"endowments": [], "curr": aggressionFactor[0], "min": aggressionFactor[0], "max": aggressionFactor[1]},
                          "baseInterestRate": {"endowments": [], "curr": baseInterestRate[0], "min": baseInterestRate[0], "max": baseInterestRate[1]},
                          "ethicalFactor": {"endowments": [], "curr": ethicalFactor[0], "min": ethicalFactor[0], "max": ethicalFactor[1]},
                          "femaleInfertilityAge": {"endowments": [], "curr": femaleInfertilityAge[0], "min": femaleInfertilityAge[0], "max": femaleInfertilityAge[1]},
                          "femaleFertilityAge": {"endowments": [], "curr": femaleFertilityAge[0], "min": femaleFertilityAge[0], "max": femaleFertilityAge[1]},
                          "fertilityFactor": {"endowments": [], "curr": fertilityFactor[0], "min": fertilityFactor[0], "max": fertilityFactor[1]},
                          "lendingFactor": {"endowments": [], "curr": lendingFactor[0], "min": lendingFactor[0], "max": lendingFactor[1]},
                          "loanDuration": {"endowments": [], "curr": loanDuration[0], "min": loanDuration[0], "max": loanDuration[1]},
                          "lookaheadFactor": {"endowments": [], "curr": lookaheadFactor[0], "min": lookaheadFactor[0], "max": lookaheadFactor[1]},
                          "maleInfertilityAge": {"endowments": [], "curr": maleInfertilityAge[0], "min": maleInfertilityAge[0], "max": maleInfertilityAge[1]},
                          "maleFertilityAge": {"endowments": [], "curr": maleFertilityAge[0], "min": maleFertilityAge[0], "max": maleFertilityAge[1]},
                          "maxAge": {"endowments": [], "curr": maxAge[0], "min": maxAge[0], "max": maxAge[1]},
                          "maxFriends": {"endowments": [], "curr": maxFriends[0], "min": maxFriends[0], "max": maxFriends[1]},
                          "movement": {"endowments": [], "curr": movement[0], "min": movement[0], "max": movement[1]},
                          "spice": {"endowments": [], "curr": startingSpice[0], "min": startingSpice[0], "max": startingSpice[1]},
                          "spiceMetabolism": {"endowments": [], "curr": spiceMetabolism[0], "min": spiceMetabolism[0], "max": spiceMetabolism[1]},
                          "sugar": {"endowments": [], "curr": startingSugar[0], "min": startingSugar[0], "max": startingSugar[1]},
                          "sugarMetabolism": {"endowments": [], "curr": sugarMetabolism[0], "min": sugarMetabolism[0], "max": sugarMetabolism[1]},
                          "tradeFactor": {"endowments": [], "curr": tradeFactor[0], "min": tradeFactor[0], "max": tradeFactor[1]},
                          "vision": {"endowments": [], "curr": vision[0], "min": vision[0], "max": vision[1]}
                          }

        for config in configurations:
            configMin = configurations[config]["min"]
            configMax = configurations[config]["max"]
            configMinDecimals = str(configMin).split('.')
            configMaxDecimals = str(configMax).split('.')
            decimalRange = []
            if len(configMinDecimals) == 2:
                configMinDecimals = len(configMinDecimals[1])
                decimalRange.append(configMinDecimals)
            if len(configMaxDecimals) == 2:
                configMaxDecimals = len(configMaxDecimals[1])
                decimalRange.append(configMaxDecimals)
            # If no fractional component to configuration item, assume increment of 1
            decimals = max(decimalRange) if len(decimalRange) > 0 else 0
            increment = 10 ** (-1 * decimals)
            configurations[config]["inc"] = increment

        endowments = []
        sexes = []
        tags = []
        immuneSystems = []
        
        sexDistributionCountdown = numAgents
        # Determine count of male agents and set as switch for agent generation
        if maleToFemaleRatio != None and maleToFemaleRatio != 0:
            sexDistributionCountdown = math.floor(sexDistributionCountdown / (maleToFemaleRatio + 1)) * maleToFemaleRatio
        
        for i in range(numAgents):
            for config in configurations:
                configurations[config]["endowments"].append(configurations[config]["curr"])
                configurations[config]["curr"] += 1
                if configurations[config]["curr"] > configurations[config]["max"]:
                    configurations[config]["curr"] = configurations[config]["min"]

            if tagStringLength > 0:
                tags.append([random.randrange(2) for i in range(tagStringLength)])
            else:
                tags.append(None)
            if immuneSystemLength > 0:
                immuneSystems.append([random.randrange(2) for i in range(immuneSystemLength)])
            else:
                immuneSystems.append(None)

            if maleToFemaleRatio != None and maleToFemaleRatio != 0:
                if sexDistributionCountdown == 0:
                    sexes.append("female")
                else:
                    sexes.append("male")
                    sexDistributionCountdown -= 1
            else:
                sexes.append(None)

        for config in configurations:
            random.shuffle(configurations[config]["endowments"])
        random.shuffle(sexes)
        for i in range(numAgents):
            agentEndowment = {"seed": self.__seed, "sex": sexes[i], "tags": tags.pop(),
                              "immuneSystem": immuneSystems.pop(), "inheritancePolicy": inheritancePolicy}
            for config in configurations:
                # If sexes are enabled, ensure proper fertility and infertility ages are set
                if sexes[i] == "female" and config == "femaleFertilityAge":
                    agentEndowment["fertilityAge"] = configurations["femaleFertilityAge"]["endowments"].pop()
                elif sexes[i] == "female" and config == "femaleInfertilityAge":
                    agentEndowment["infertilityAge"] = configurations["femaleInfertilityAge"]["endowments"].pop()
                elif sexes[i] == "male" and config == "maleFertilityAge":
                    agentEndowment["fertilityAge"] = configurations["maleFertilityAge"]["endowments"].pop()
                elif sexes[i] == "male" and config == "maleInfertilityAge":
                    agentEndowment["infertilityAge"] = configurations["maleInfertilityAge"]["endowments"].pop()
                elif sexes[i] == None and (config == "femaleInfertilityAge" or config == "femaleFertilityAge" or
                                           config == "maleInfertilityAge" or config == "maleFertilityAge"):
                    continue
                else:
                    agentEndowment[config] = configurations[config]["endowments"].pop()
            
            if sexes[i] == None:
                agentEndowment["fertilityAge"] = 0
                agentEndowment["infertilityAge"] = 0
            endowments.append(agentEndowment)
        return endowments

    def removeDeadAgents(self):
        deadAgents = []
        for agent in self.__agents:
            if agent.isAlive() == False:
                deadAgents.append(agent)
            elif agent.getCell() == None:
                deadAgents.append(agent)
        for agent in deadAgents:
            self.__agents.remove(agent)

    def replaceDeadAgents(self):
        numAgents = len(self.__agents)
        if numAgents < self.__configuration["agentReplacements"]:
            numReplacements = self.__configuration["agentReplacements"] - numAgents
            self.configureAgents(numReplacements)
            if self.__gui != None:
                self.__gui.doTimestep()

    def runSimulation(self, timesteps=5):
        self.startLog()
        if self.__gui != None:
            self.pauseSimulation() # Simulation begins paused until start button in GUI pressed
        t = 0
        timesteps = timesteps - self.__timestep
        while t <= timesteps and len(self.__agents) > 0:
            self.doTimestep()
            t += 1
            if self.__gui != None and self.__run == False:
                self.pauseSimulation()
        self.endSimulation()

    def setAgents(self, agents):
        self.__agents = agents

    def setEnd(self):
        self.__end = not self.__end

    def setEnvironment(self, environment):
        self.__environment = environment

    def setEnvironmentHeight(self, environmentHeight):
        self.__environmentHeight = environmentHeight

    def setEnvironmentWidth(self, environmentWidth):
        self.__environmentWidth = environmentWidth

    def setGUI(self, gui):
        self.__gui = gui

    def setTimestep(self, timestep):
        self.__timestep = timestep
  
    def setRun(self):
        self.__run = not self.__run
  
    def setRuntimeStats(self, runtimeStats):
        self.__runtimeStats = runtimeStats

    def startLog(self):
        if self.__log == None:
            return
        self.__log.write("[\n")

    def updateGiniCoefficient(self):
        agentWealths = sorted([agent.getWealth() for agent in self.__agents])
        # Calculate area between line of equality and Lorenz curve of agent wealths
        height = 0
        area = 0
        for wealth in agentWealths:
            height += wealth
            area += (height - wealth) / 2
        lineOfEquality = (height * len(agentWealths)) / 2
        giniCoefficient = (lineOfEquality - area) / max(1, lineOfEquality)
        return giniCoefficient

    def updateRuntimeStats(self):
        numAgents = len(self.__agents)
        meanSugarMetabolism = 0
        meanSpiceMetabolism = 0
        meanMetabolism = 0
        meanVision = 0
        meanWealth = 0
        meanAge = 0
        meanTradePrice = 0
        meanTradeVolume = 0
        totalTradeVolume = 0
        totalWealth = 0
        maxWealth = 0
        minWealth = sys.maxsize
        for agent in self.__agents:
            agentWealth = agent.getWealth()
            meanSugarMetabolism += agent.getSugarMetabolism()
            meanSpiceMetabolism += agent.getSpiceMetabolism()
            meanVision += agent.getVision()
            meanAge += agent.getAge()
            meanWealth += agentWealth
            totalWealth += agentWealth
            if agentWealth < minWealth:
                minWealth = agentWealth
            if agentWealth > maxWealth:
                maxWealth = agentWealth
        if numAgents > 0:
            combinedMetabolism = meanSugarMetabolism + meanSpiceMetabolism 
            if meanSugarMetabolism > 0 and meanSpiceMetabolism > 0:
                combinedMetabolism = combinedMetabolism / 2
            meanMetabolism = combinedMetabolism / numAgents
            meanVision = meanVision / numAgents
            meanAge = meanAge / numAgents
            meanWealth = meanWealth / numAgents
        else:
            meanMetabolism = 0
            meanVision = 0
            meanAge = 0
            meanWealth = 0
        self.__runtimeStats["timestep"] = self.__timestep
        self.__runtimeStats["agents"] = numAgents
        self.__runtimeStats["meanMetabolism"] = meanMetabolism
        self.__runtimeStats["meanVision"] = meanVision
        self.__runtimeStats["meanAge"] = meanAge
        self.__runtimeStats["meanWealth"] = meanWealth
        self.__runtimeStats["minWealth"] = minWealth
        self.__runtimeStats["maxWealth"] = maxWealth
        self.__runtimeStats["giniCoefficient"] = self.updateGiniCoefficient() if len(self.__agents) > 1 else 0

    def writeToLog(self):
        self.__lastLoggedTimestep = self.__timestep
        if self.__log == None:
            return
        logString = '\t' + json.dumps(self.__runtimeStats) + ",\n"
        self.__log.write(logString)

    def __str__(self):
        string = "{0}Seed: {1}\nTimestep: {2}\nLiving Agents: {3}".format(str(self.__environment), self.__seed, self.__lastLoggedTimestep, len(self.__agents))
        return string

def parseConfiguration(configFile, configuration):
    file = open(configFile)
    options = json.loads(file.read())
    for opt in configuration:
        if opt in options:
            configuration[opt] = options[opt]
    return configuration

def parseOptions(configuration):
    commandLineArgs = sys.argv[1:]
    shortOptions = "ch:"
    longOptions = ["conf=", "help"]
    try:
        args, vals = getopt.getopt(commandLineArgs, shortOptions, longOptions)
    except getopt.GetoptError as err:
        print(err)
        printHelp()
    nextArg = 0
    for currArg, currVal in args:
        nextArg += 1
        if currArg in("-c", "--conf"):
            if currArg == "-c" and nextArg < len(commandLineArgs):
                currVal = commandLineArgs[nextArg]
            if currVal == "":
                print("No config file provided.")
                printHelp()
            parseConfiguration(currVal, configuration)
        elif currArg in ("-h", "--help"):
            printHelp()
    return configuration

def printHelp():
    print("Usage:\n\tpython sugarscape.py --conf config.json\n\nOptions:\n\t-c,--conf\tUse specified config file for simulation settings.\n\t-h,--help\tDisplay this message.")
    exit(0)

def verifyConfiguration(configuration):
    # Ensure starting agents are not larger than available cells
    totalCells = configuration["environmentHeight"] * configuration["environmentWidth"]
    if configuration["startingAgents"] > totalCells:
        print("Could not allocate {0} agents. Allocating maximum of {1}.".format(configuration["startingAgents"], totalCells))
        configuration["startingAgents"] = totalCells

    # Ensure infinitely-lived agents are properly initialized
    if configuration["agentMaxAge"][0] < 0 or configuration["agentMaxAge"][1] < 0:
        configuration["agentMaxAge"][0] = -1
        configuration["agentMaxAge"][1] = -1

    # Ensure at most number of tribes equal to agent tag string length
    if configuration["agentTagStringLength"] > 0 and configuration["environmentMaxTribes"] > configuration["agentTagStringLength"]:
            configuration["environmentMaxTribes"] = configuration["agentTagStringLength"]
    if configuration["environmentMaxTribes"] > 11:
        configuration["environmentMaxTribes"] = 11

    if len(configuration["agentStartingQuadrants"]) == 0:
        configuration["agentStartingQuadrants"] = [1, 2, 3, 4]

    # Set timesteps to (seemingly) unlimited runtime
    if configuration["timesteps"] < 0:
        configuration["timesteps"] = sys.maxsize

    if configuration["seed"] == -1:
        configuration["seed"] = random.randrange(sys.maxsize)

    if configuration["logfile"] == "":
        configuration["logfile"] = None
    return configuration

if __name__ == "__main__":
    # Set default values for simulation configuration
    configuration = {"agentAggressionFactor": [0, 0],
                     "agentBaseInterestRate": [0.0, 0.0],
                     "agentEthicalFactor": [0, 0],
                     "agentFemaleInfertilityAge": [0, 0],
                     "agentFemaleFertilityAge": [0, 0],
                     "agentFertilityFactor": [0, 0],
                     "agentImmuneSystemLength": 0,
                     "agentInheritancePolicy": "none",
                     "agentLendingFactor": [0, 0],
                     "agentLoanDuration": [0, 0],
                     "agentLookaheadFactor": [0, 0],
                     "agentMaleInfertilityAge": [0, 0],
                     "agentMaleFertilityAge": [0, 0],
                     "agentMaleToFemaleRatio": 1.0,
                     "agentMaxAge": [-1, -1],
                     "agentMaxFriends": [0, 0],
                     "agentMovement": [1, 6],
                     "agentReplacements": 0,
                     "agentSpiceMetabolism": [0, 0],
                     "agentStartingSpice": [0, 0],
                     "agentStartingSugar": [10, 40],
                     "agentStartingQuadrants": [1, 2, 3, 4],
                     "agentSugarMetabolism": [1, 4],
                     "agentTagStringLength": 0,
                     "agentTradeFactor": [0, 0],
                     "agentVision": [1, 6],
                     "diseaseAggressionPenalty": [0, 0],
                     "diseaseFertilityPenalty": [0, 0],
                     "diseaseMovementPenalty": [0, 0],
                     "diseaseSpiceMetabolismPenalty": [0, 0],
                     "diseaseSugarMetabolismPenalty": [0, 0],
                     "diseaseTagStringLength": [0, 0],
                     "diseaseVisionPenalty": [0, 0],
                     "environmentHeight": 50,
                     "environmentMaxCombatLoot": 0,
                     "environmentMaxSpice": 0,
                     "environmentMaxSugar": 4,
                     "environmentMaxTribes": 0,
                     "environmentPollutionDiffusionDelay": 0,
                     "environmentSeasonalGrowbackDelay": 0,
                     "environmentSeasonInterval": 0,
                     "environmentSpiceConsumptionPollutionFactor": 0,
                     "environmentSpiceProductionPollutionFactor": 0,
                     "environmentSpiceRegrowRate": 0,
                     "environmentSugarConsumptionPollutionFactor": 0,
                     "environmentSugarProductionPollutionFactor": 0,
                     "environmentSugarRegrowRate": 1,
                     "environmentWidth": 50,
                     "headlessMode": False,
                     "logfile": None,
                     "seed": -1,
                     "startingAgents": 250,
                     "startingDiseases": 0,
                     "timesteps": 200}
    configuration = parseOptions(configuration)
    configuration = verifyConfiguration(configuration)
    random.seed(configuration["seed"])
    S = Sugarscape(configuration)
    S.runSimulation(configuration["timesteps"])
    exit(0)
